"""Check the OpenAI models this app uses for announced shutdowns.

Finds the model IDs used by the backend, asks the Models API for each one's `shutdown_date`, and looks up the
recommended replacement on OpenAI's deprecations page. With --apply, rewrites deprecated IDs to their replacement
in the source, .env.example and docs so CI can open a PR (.github/workflows/model-deprecations.yml).

Standard library only, so CI can run it without installing the backend.

    python tools/check_model_deprecations.py                          # report only
    python tools/check_model_deprecations.py --apply --report out.md  # rewrite files, save report

The API key comes from OPENAI_API_KEY, falling back to backend/.env.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "backend" / "core", ROOT / "backend" / "server"]
ENV_FILE = ROOT / "backend" / ".env"
# Rewritten by --apply in addition to the source files a deprecated model was found in.
EXTRA_REWRITE_GLOBS = ["backend/.env.example", "README.md", "backend/README.md", "design_doc/**/*.md", "docs/**/*.md"]

MODELS_URL = "https://api.openai.com/v1/models"
DEPRECATIONS_MD_URL = "https://developers.openai.com/api/docs/deprecations.md"
DEPRECATIONS_PAGE_URL = "https://developers.openai.com/api/docs/deprecations"

# Names like openai_model_chat / openai_image_model / _EMBED_MODEL hold a model ID.
_MODEL_NAME = re.compile(r"(^|_)model($|_)", re.IGNORECASE)
_TABLE_CELL_SPLIT = re.compile(r"(?<!\\)\|")  # `\|` separates aliases inside a cell
_TICKED = re.compile(r"`([^`]+)`")
_SNAPSHOT_SUFFIX = r"-\d{4}-\d{2}-\d{2}"


@dataclass
class Finding:
    model: str
    locations: list[str]
    available: bool
    shutdown_date: str | None
    recommended: list[str] = field(default_factory=list)
    replacement: str | None = None


def _http_get(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "model-deprecation-check", **(headers or {})})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _read_env_file() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep and not name.lstrip().startswith("#"):
            values[name.strip()] = value.strip().strip("\"'")
    return values


def fetch_models(api_key: str) -> dict[str, str | None]:
    """Model ID -> shutdown_date (YYYY-MM-DD, or None if no shutdown is announced)."""
    data = json.loads(_http_get(MODELS_URL, {"Authorization": f"Bearer {api_key}"}))
    return {model["id"]: model.get("shutdown_date") for model in data["data"]}


def find_used_models(known_ids: set[str], env_values: dict[str, str]) -> dict[str, list[tuple[Path, str]]]:
    """Model ID -> [(file, display location)].

    A string is treated as a model ID if it is assigned to a *model* name or passed as model=..., or if it is any
    string literal that matches a model the API key can see. The first rule also catches IDs that have already
    disappeared from the model list.
    """
    used: dict[str, list[tuple[Path, str]]] = {}

    def add(model_id: str, path: Path, where: str) -> None:
        used.setdefault(model_id, []).append((path, where))

    for base in SCAN_DIRS:
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=rel)
            named: set[int] = set()
            for node in ast.walk(tree):
                value = None
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    if _MODEL_NAME.search(node.target.id):
                        value = node.value
                elif isinstance(node, ast.Assign):
                    if any(isinstance(t, ast.Name) and _MODEL_NAME.search(t.id) for t in node.targets):
                        value = node.value
                elif isinstance(node, ast.keyword) and node.arg == "model":
                    value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    named.add(id(value))
                    add(value.value, path, f"{rel}:{value.lineno}")
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value in known_ids
                    and id(node) not in named
                ):
                    add(node.value, path, f"{rel}:{node.lineno}")

    # Local overrides only; CI has no .env. Never rewritten, since the file is not tracked.
    for name, value in env_values.items():
        if name.startswith("OPENAI_") and "MODEL" in name and value:
            add(value, ENV_FILE, f"backend/.env ({name})")
    return used


def parse_deprecation_tables(markdown: str) -> list[tuple[list[str], list[str]]]:
    """[(deprecated model IDs, recommended replacement IDs)] for every table row on the deprecations page."""
    rows: list[tuple[list[str], list[str]]] = []
    header: list[str] | None = None
    model_col = replacement_col = None
    for line in markdown.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in _TABLE_CELL_SPLIT.split(line.strip().strip("|"))]
        if header is None:
            header = [cell.lower() for cell in cells]
            model_col = next((i for i, h in enumerate(header) if "model" in h and "price" not in h), None)
            replacement_col = next((i for i, h in enumerate(header) if "replacement" in h or "substitute" in h), None)
            continue
        if model_col is None or replacement_col is None or max(model_col, replacement_col) >= len(cells):
            continue
        if not set("".join(cells)) - set("-: "):  # | --- | separator row
            continue
        rows.append((_TICKED.findall(cells[model_col]), _TICKED.findall(cells[replacement_col])))
    return rows


def recommended_replacements(model_id: str, rows: list[tuple[list[str], list[str]]]) -> list[str]:
    """Replacements listed for model_id, or for one of its dated snapshots (gpt-4o-mini -> gpt-4o-mini-2024-07-18)."""
    snapshot = re.compile(re.escape(model_id) + _SNAPSHOT_SUFFIX + "$")
    exact = [repl for ids, repl in rows if model_id in ids and repl]
    by_snapshot = [repl for ids, repl in rows if repl and any(snapshot.match(i) for i in ids)]
    return (exact or by_snapshot or [[]])[0]


def _id_pattern(model_id: str) -> re.Pattern[str]:
    # Whole IDs only: gpt-4o-mini must not match gpt-4o-mini-tts, gpt-image-1 must not match gpt-image-1.5.
    return re.compile(rf"(?<![\w.-]){re.escape(model_id)}(?![\w-]|\.\d)")


def apply_replacements(findings: list[Finding], used: dict[str, list[tuple[Path, str]]]) -> list[str]:
    replacements = {f.model: f.replacement for f in findings if f.replacement}
    if not replacements:
        return []
    targets = {path for model_id in replacements for path, _ in used[model_id] if path != ENV_FILE}
    for pattern in EXTRA_REWRITE_GLOBS:
        targets.update(ROOT.glob(pattern))

    changed: list[str] = []
    for path in sorted(targets):
        if not path.is_file():
            continue
        # Bytes in/out so line endings and any BOM are preserved.
        text = path.read_bytes().decode("utf-8")
        new_text = text
        for old, new in replacements.items():
            new_text = _id_pattern(old).sub(new, new_text)
        if new_text != text:
            path.write_bytes(new_text.encode("utf-8"))
            changed.append(path.relative_to(ROOT).as_posix())
    return changed


def build_report(findings: list[Finding], today: dt.date) -> str:
    if not findings:
        return f"廃止予定・利用不可の OpenAI モデルはありません（{today} 時点）。\n"

    lines = [
        "## 廃止予定・利用不可の OpenAI モデル",
        "",
        f"`tools/check_model_deprecations.py` の検出結果です（{today} 時点）。",
        "",
        "| モデル | 停止日 | 使用箇所 | 置き換え先 |",
        "| --- | --- | --- | --- |",
    ]
    for f in findings:
        if not f.available:
            status = "**モデル一覧にない（利用不可）**"
        else:
            days = (dt.date.fromisoformat(f.shutdown_date) - today).days
            status = f"{f.shutdown_date}（**停止済み**）" if days < 0 else f"{f.shutdown_date}（あと {days} 日）"
        others = [r for r in f.recommended if r != f.replacement]
        if f.replacement and others:
            replacement = f"`{f.replacement}`（他の候補: {', '.join(f'`{r}`' for r in others)}）"
        elif f.replacement:
            replacement = f"`{f.replacement}`"
        elif f.recommended:
            listed = ", ".join(f"`{r}`" for r in f.recommended)
            replacement = f"要手動対応（推奨の {listed} はこのキーで使えないか廃止予定）"
        else:
            replacement = "要手動対応（推奨が見つからない）"
        lines.append(f"| `{f.model}` | {status} | {'<br>'.join(f.locations)} | {replacement} |")
    lines += [
        "",
        f"置き換え先は [OpenAI Deprecations]({DEPRECATIONS_PAGE_URL}) の推奨のうち、"
        "このAPIキーで使えて廃止予定のないものを機械的に選んでいます。",
        "",
        "### マージ前に確認すること",
        "",
        "- モデル名を置換しただけで、エンドポイントやパラメータの互換性は確認していません。"
        "該当する機能を実際に動かして確認してください。",
        "- `backend/.env` でモデルを上書きしている場合は、そちらも手動で変更してください。",
    ]
    return "\n".join(lines) + "\n"


def _set_github_outputs(**values: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            for key, value in values.items():
                fh.write(f"{key}={str(value).lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="rewrite deprecated model IDs to their replacement")
    parser.add_argument("--report", type=Path, help="also write the Markdown report to this file")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")

    env_values = _read_env_file()
    api_key = os.environ.get("OPENAI_API_KEY") or env_values.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not set (environment or backend/.env)", file=sys.stderr)
        return 2

    models = fetch_models(api_key)
    used = find_used_models(set(models), env_values)
    flagged = [m for m in sorted(used) if m not in models or models[m]]

    rows = parse_deprecation_tables(_http_get(DEPRECATIONS_MD_URL).decode("utf-8")) if flagged else []
    findings: list[Finding] = []
    for model_id in flagged:
        recommended = recommended_replacements(model_id, rows)
        usable = [r for r in recommended if r in models and not models[r]]
        findings.append(
            Finding(
                model=model_id,
                locations=sorted({where for _, where in used[model_id]}),
                available=model_id in models,
                shutdown_date=models.get(model_id),
                recommended=recommended,
                replacement=usable[0] if usable else None,
            )
        )

    report = build_report(findings, dt.date.today())
    print(report)
    if args.report:
        args.report.write_text(report, encoding="utf-8")

    changed = apply_replacements(findings, used) if args.apply else []
    if changed:
        print("Rewrote:\n" + "\n".join(f"  {path}" for path in changed))
    _set_github_outputs(
        has_findings=bool(findings),
        has_changes=bool(changed),
        needs_manual=any(f.replacement is None for f in findings),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
