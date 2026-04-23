from __future__ import annotations

from core.services.scraper.wiktionary import WiktionaryScraper

NOISE_TOKENS = {"of", "from", "for", "to", "by", "and", "or", "the", "a", "an"}
FORM_KEYS = (
    "third_person_singular",
    "present_participle",
    "past_tense",
    "past_participle",
    "plural",
    "comparative",
    "superlative",
)
MARKERS = {"er", "est", "more", "most"}


def regular_adj_forms(word: str) -> tuple[str, str]:
    lower = word.lower()
    if lower.endswith("y") and len(word) > 1 and lower[-2] not in "aeiou":
        return f"{word[:-1]}ier", f"{word[:-1]}iest"
    if lower.endswith("e"):
        return f"{word}r", f"{word}st"
    return f"{word}er", f"{word}est"


def normalize_marker_forms(word: str, forms: dict) -> dict:
    next_forms = dict(forms)
    c_raw = str(forms.get("comparative", "")).strip()
    s_raw = str(forms.get("superlative", "")).strip()
    c = c_raw.lower()
    s = s_raw.lower()
    if c not in MARKERS and s not in MARKERS:
        return next_forms
    reg_c, reg_s = regular_adj_forms(word)
    if c == "er" and s == "more":
        next_forms["comparative"] = f"more {word}"
        next_forms["superlative"] = f"most {word}"
        return next_forms
    if c == "er":
        next_forms["comparative"] = reg_c
    if s == "est":
        next_forms["superlative"] = reg_s
    return next_forms


def has_noise(forms: object) -> bool:
    if not isinstance(forms, dict):
        return False
    for key in FORM_KEYS:
        value = forms.get(key)
        if isinstance(value, str) and value.strip().lower() in NOISE_TOKENS:
            return True
    return False


async def refresh_forms_from_wiktionary(word_text: str, forms: dict) -> dict:
    scraper = WiktionaryScraper()
    scraped = await scraper.scrape(word_text)
    next_forms = scraped.get("forms", {}) if isinstance(scraped, dict) else {}
    if not isinstance(next_forms, dict):
        next_forms = {}
    if has_noise(next_forms):
        for key in FORM_KEYS:
            value = next_forms.get(key)
            if isinstance(value, str) and value.strip().lower() in NOISE_TOKENS:
                next_forms.pop(key, None)
    return next_forms if next_forms else forms
