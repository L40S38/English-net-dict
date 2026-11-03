from __future__ import annotations

import difflib

try:
    from spellchecker import SpellChecker
except Exception:  # noqa: BLE001
    SpellChecker = None  # type: ignore[assignment]


def build_spellchecker(
    words: list[str],
    *,
    merge_db_vocabulary: bool = False,
) -> SpellChecker | None:
    if SpellChecker is None:
        return None
    try:
        checker = SpellChecker()
        if merge_db_vocabulary:
            checker.word_frequency.load_words(words)
        return checker
    except Exception:  # noqa: BLE001
        return None


def collect_spelling_suggestions(
    word_text: str,
    by_lower: dict[str, str],
    spellchecker: SpellChecker | None,
    *,
    use_db_near: bool = False,
    db_near_n: int = 6,
    db_near_cutoff: float = 0.84,
    pyspell_max_out: int = 8,
) -> list[dict[str, str]]:
    target = word_text.strip().lower()
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    if use_db_near:
        for candidate in difflib.get_close_matches(
            target,
            list(by_lower.keys()),
            n=db_near_n,
            cutoff=db_near_cutoff,
        ):
            surface = by_lower.get(candidate) or candidate
            key = surface.lower()
            if key == target or key in seen:
                continue
            seen.add(key)
            out.append({"spelling": surface, "source": "db_near"})

    if spellchecker is not None:
        try:
            spelled = set(spellchecker.candidates(target) or set())
        except Exception:  # noqa: BLE001
            spelled = set()
        try:
            corrected = spellchecker.correction(target)
            if corrected:
                spelled.add(corrected)
        except Exception:  # noqa: BLE001
            pass
        for candidate in sorted(spelled):
            key = candidate.strip().lower()
            if not key or key == target or key in seen:
                continue
            seen.add(key)
            out.append({"spelling": by_lower.get(key) or candidate, "source": "pyspellchecker"})
            if len(out) >= pyspell_max_out:
                break
    return out
