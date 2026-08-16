from functools import lru_cache
from pathlib import Path

PROMPT_VERSION = "v1"
APP_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
LEGACY_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache(maxsize=32)
def load_prompt(filename: str) -> str:
    # Prefer app/prompts, fallback to legacy backend/prompts for compatibility.
    primary = APP_PROMPTS_DIR / filename
    if primary.exists():
        return primary.read_text(encoding="utf-8")
    legacy = LEGACY_PROMPTS_DIR / filename
    if legacy.exists():
        return legacy.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt file not found: {primary} (or legacy {legacy})")
