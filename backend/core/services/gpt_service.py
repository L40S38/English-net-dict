from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from core.config import settings
from core.services.example_cache import get_cached_example, make_cache_key, save_cached_example
from core.utils.pos_labels import normalize_part_of_speech
from core.utils.prompt_loader import PROMPT_VERSION, load_prompt
from core.utils.text_repair import repair_nested_strings, repair_text


def _wiktionary_items(scraped_data: list[dict]) -> list[dict]:
    return [item for item in scraped_data if str(item.get("source", "")).startswith("wiktionary_")]


def _pick_first_str(scraped_data: list[dict], key: str) -> str | None:
    for item in _wiktionary_items(scraped_data):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _pick_first_list(scraped_data: list[dict], key: str) -> list[str]:
    for item in _wiktionary_items(scraped_data):
        value = item.get(key)
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
    return []


def _normalize_phrase_entries(raw_phrases: object) -> list[dict[str, str]]:
    if not isinstance(raw_phrases, list):
        return []
    entries: list[dict[str, str]] = []
    for item in raw_phrases:
        if isinstance(item, str):
            phrase = item.strip()
            if phrase:
                entries.append({"phrase": phrase, "meaning": ""})
            continue
        if not isinstance(item, dict):
            continue
        phrase = str(item.get("phrase", item.get("text", ""))).strip()
        if not phrase:
            continue
        meaning = str(item.get("meaning", item.get("meaning_en", item.get("meaning_ja", "")))).strip()
        entries.append({"phrase": phrase, "meaning": meaning})
    return entries


def _phrase_entries_from_strings(raw_phrases: list[str]) -> list[dict[str, str]]:
    return [{"phrase": p.strip(), "meaning": ""} for p in raw_phrases if p and p.strip()]


def _pick_forms(scraped_data: list[dict]) -> dict:
    for item in _wiktionary_items(scraped_data):
        value = item.get("forms")
        if isinstance(value, dict):
            return value
    return {}


def _pick_first_dict_list(scraped_data: list[dict], key: str) -> list[dict]:
    for item in _wiktionary_items(scraped_data):
        value = item.get(key)
        if isinstance(value, list):
            cleaned = [x for x in value if isinstance(x, dict)]
            if cleaned:
                return cleaned
    return []


def _pick_wiktionary_definitions(scraped_data: list[dict], word: str) -> list[dict]:
    definitions = _pick_first_dict_list(scraped_data, "definitions")
    if not definitions:
        return []
    cleaned: list[dict] = []
    for idx, item in enumerate(definitions[:8]):
        part_of_speech = normalize_part_of_speech(str(item.get("part_of_speech", "noun")))
        meaning_en = str(item.get("meaning_en", "")).strip()
        if not meaning_en:
            continue
        example_en = str(item.get("example_en", "")).strip()
        if not example_en:
            example_en = f"This is an example using {word} (sense {idx + 1})."
        cleaned.append(
            {
                "part_of_speech": part_of_speech,
                "meaning_en": meaning_en,
                "meaning_ja": "",
                "example_en": example_en,
                "example_ja": "",
                "sort_order": idx,
            }
        )
    return cleaned


def _best_component_meaning(component_text: str, component_meanings: list[dict]) -> str | None:
    text = component_text.strip().lower()
    if not text:
        return None
    generic = {"語源要素", "語根要素", "接頭要素"}
    for item in component_meanings:
        if not isinstance(item, dict):
            continue
        key = str(item.get("text", "")).strip().lower()
        meaning = str(item.get("meaning", "")).strip()
        if key == text and meaning and meaning not in generic:
            return meaning
    return None


def _merge_component_meanings_into_components(components: list[dict], component_meanings: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for comp in components:
        if not isinstance(comp, dict):
            continue
        item = dict(comp)
        replacement = _best_component_meaning(str(item.get("text", "")), component_meanings)
        if replacement:
            item["meaning"] = replacement
        merged.append(item)
    return merged


def _guess_etymology_components(scraped_data: list[dict]) -> list[dict]:
    for item in _wiktionary_items(scraped_data):
        comps = item.get("etymology_components")
        if isinstance(comps, list) and comps:
            cleaned = [x for x in comps if isinstance(x, dict) and x.get("text")]
            if cleaned:
                return cleaned

    excerpt = _pick_first_str(scraped_data, "etymology_excerpt") or ""
    if not excerpt:
        return []
    # Example: "formed from a + bandon"
    match = re.search(r"formed from\s+([A-Za-z-]+)\s*\+\s*([A-Za-z-]+)", excerpt, flags=re.IGNORECASE)
    if not match:
        return []
    left = match.group(1)
    right = match.group(2)
    prefix_meanings = {
        "a": "〜へ、〜の方へ",
        "ab": "〜から離れて",
        "ad": "〜へ",
    }
    left_meaning = prefix_meanings.get(left.lower(), "接頭要素")
    return [
        {"text": left, "meaning": left_meaning, "type": "prefix"},
        {"text": right, "meaning": "語根要素", "type": "root"},
    ]


def _build_fallback_etymology_description(word: str, scraped_data: list[dict]) -> str:
    for item in scraped_data:
        source = str(item.get("source", ""))
        if source.startswith("wiktionary_"):
            excerpt = item.get("etymology_excerpt")
            if isinstance(excerpt, str) and excerpt.strip():
                return f"Wiktionary ({source}) etymology: {excerpt.strip()}"
            summary = item.get("summary")
            if isinstance(summary, str) and summary.strip():
                return f"Wiktionary ({source}) summary: {summary[:600].strip()}"

    for item in scraped_data:
        summary = item.get("summary")
        source = str(item.get("source", "unknown"))
        if isinstance(summary, str) and summary.strip():
            return f"{source} summary: {summary[:600].strip()}"

    return f"Etymology summary for {word}."


def _pick_example_containing_word(examples: list[str], word: str, fallback: str) -> str:
    """Use the first example that contains the target word (case-insensitive); otherwise return fallback."""
    w = word.strip().lower()
    if not w:
        return fallback
    for ex in (examples or []):
        if ex and isinstance(ex, str) and w in ex.lower():
            return ex.strip()
    return fallback


def _is_placeholder_example(example_en: str, word: str) -> bool:
    """True if example_en is empty or our generic placeholder (so we may replace with GPT)."""
    ex = (example_en or "").strip()
    if not ex:
        return True
    w = word.strip().lower()
    if not w:
        return False
    if ex.lower().startswith("this is an example using ") and w in ex.lower():
        return True
    if ex.lower().startswith("this is a simple example using ") and w in ex.lower():
        return True
    return False


def _parse_single_example_response(text: str) -> str:
    value = (text or "").strip()
    for prefix in ("```json", "```"):
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()
        if value.endswith("```"):
            value = value[:-3].strip()
    data = repair_nested_strings(json.loads(value))
    if isinstance(data, dict):
        examples = data.get("examples")
        if isinstance(examples, list) and examples:
            return str(examples[0]).strip()
        example = data.get("example")
        if isinstance(example, str):
            return example.strip()
    return ""


def _fill_empty_examples_with_gpt(word: str, definitions: list[dict]) -> None:
    """Fill definitions that have empty or placeholder example_en using GPT. Mutates definitions in place."""
    if not settings.openai_api_key or not word or not definitions:
        return
    need_list: list[tuple[int, dict]] = [
        (i, d)
        for i, d in enumerate(definitions)
        if isinstance(d, dict) and _is_placeholder_example(d.get("example_en", ""), word)
    ]
    if not need_list:
        return
    prompt = load_prompt("example_sentence.md")
    model = settings.openai_model_structured
    client = OpenAI(api_key=settings.openai_api_key)
    w_lower = word.strip().lower()

    for i, d in need_list:
        payload = {
            "target_word": word,
            "definitions": [{"meaning_en": d.get("meaning_en", ""), "part_of_speech": d.get("part_of_speech", "")}],
        }
        user_content = json.dumps(payload, ensure_ascii=False)
        cache_key = make_cache_key(prompt, model, user_content)

        cached_example = get_cached_example(cache_key)
        if cached_example and (not w_lower or w_lower in cached_example.lower()):
            definitions[i]["example_en"] = cached_example
            continue

        try:
            completion = client.responses.create(
                model=model,
                temperature=0.0,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            ex = _parse_single_example_response(completion.output_text or "")
            if ex and w_lower in ex.lower():
                definitions[i]["example_en"] = ex
                save_cached_example(cache_key, ex)
        except Exception:  # noqa: BLE001
            continue


def _fallback_structured(word: str, wordnet_data: dict, scraped_data: list[dict]) -> dict:
    default_example = f"This is a simple example using {word}."
    definitions = _pick_wiktionary_definitions(scraped_data, word)
    if not definitions:
        definitions = []
        for i, entry in enumerate(wordnet_data.get("entries", [])[:4]):
            examples = entry.get("examples") or [default_example]
            example_en = _pick_example_containing_word(examples, word, default_example)
            if example_en == default_example:
                example_en = f"This is a simple example using {word} (sense {i + 1})."
            definitions.append(
                {
                    "part_of_speech": normalize_part_of_speech(entry.get("part_of_speech", "noun")),
                    "meaning_en": entry.get("definition", f"Meaning of {word}"),
                    "meaning_ja": "",
                    "example_en": example_en,
                    "example_ja": "",
                    "sort_order": i,
                }
            )
    if not definitions:
        definitions = [
            {
                "part_of_speech": normalize_part_of_speech("noun"),
                "meaning_en": f"Core meaning of {word}",
                "meaning_ja": f"{word} の基本的な意味",
                "example_en": f"I am learning the word {word}.",
                "example_ja": f"私は {word} という単語を学んでいます。",
                "sort_order": 0,
            }
        ]
    _fill_empty_examples_with_gpt(word, definitions)
    synonyms = [str(s).strip() for s in wordnet_data.get("synonyms", []) if str(s).strip()][:6]
    if not synonyms:
        synonyms = _pick_first_list(scraped_data, "synonyms")[:6]
    antonyms = _pick_first_list(scraped_data, "antonyms")[:6]
    derived_terms = _pick_first_list(scraped_data, "derived_terms")[:8]
    phrases = _pick_first_list(scraped_data, "phrases")[:8]
    forms = _pick_forms(scraped_data)
    normalized_form_phrases = _normalize_phrase_entries(forms.get("phrases"))
    if normalized_form_phrases:
        forms["phrases"] = normalized_form_phrases
    elif phrases:
        forms["phrases"] = _phrase_entries_from_strings(phrases)
    components = _guess_etymology_components(scraped_data)
    language_chain = _pick_first_dict_list(scraped_data, "language_chain")
    component_meanings = _pick_first_dict_list(scraped_data, "component_meanings")
    etymology_variants = _pick_first_dict_list(scraped_data, "etymology_variants")
    components = _merge_component_meanings_into_components(components, component_meanings)

    structured = {
        "phonetic": _pick_first_str(scraped_data, "pronunciation_ipa"),
        "forms": forms,
        "definitions": definitions,
        "etymology": {
            "components": components,
            "origin_word": None,
            "origin_language": None,
            "core_image": f"{word}: central concept",
            "branches": [],
            "language_chain": language_chain,
            "component_meanings": component_meanings,
            "etymology_variants": etymology_variants,
            "raw_description": _build_fallback_etymology_description(word, scraped_data),
        },
        "derivations": [
            {
                "derived_word": term,
                "part_of_speech": normalize_part_of_speech("noun"),
                "meaning_ja": "",
                "sort_order": i,
            }
            for i, term in enumerate(derived_terms)
        ],
        "related_words": (
            [{"related_word": s, "relation_type": "synonym", "note": "WordNet/Wiktionary candidate"} for s in synonyms]
            + [{"related_word": a, "relation_type": "antonym", "note": "Wiktionary candidate"} for a in antonyms]
        ),
        "prompt_version": PROMPT_VERSION,
    }
    return structured


def generate_structured_word_data(word: str, wordnet_data: dict, scraped_data: list[dict]) -> dict[str, Any]:
    if not settings.openai_api_key:
        return _fallback_structured(word, wordnet_data, scraped_data)

    prompt = load_prompt("word_structuring.md")
    client = OpenAI(api_key=settings.openai_api_key)
    payload = {
        "target_word": word,
        "wordnet_data": wordnet_data,
        "scraped_data": scraped_data,
        "prompt_version": PROMPT_VERSION,
    }
    try:
        completion = client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        text = _strip_json_code_fence(completion.output_text or "")
        data = repair_nested_strings(json.loads(text))
    except Exception:  # noqa: BLE001
        return _fallback_structured(word, wordnet_data, scraped_data)
    data.setdefault("forms", {})
    if not isinstance(data["forms"], dict):
        data["forms"] = {}
    scraped_forms = _pick_forms(scraped_data)
    for key, value in scraped_forms.items():
        data["forms"].setdefault(key, value)
    normalized_data_phrases = _normalize_phrase_entries(data["forms"].get("phrases"))
    scraped_phrases = _pick_first_list(scraped_data, "phrases")
    if normalized_data_phrases:
        data["forms"]["phrases"] = normalized_data_phrases
    elif scraped_phrases:
        data["forms"]["phrases"] = _phrase_entries_from_strings(scraped_phrases)

    for definition in data.get("definitions", []):
        definition["part_of_speech"] = normalize_part_of_speech(definition.get("part_of_speech"))
    for derivation in data.get("derivations", []):
        derivation["part_of_speech"] = normalize_part_of_speech(derivation.get("part_of_speech"))
    for comp in data.get("etymology", {}).get("components", []):
        if isinstance(comp, dict) and "text" not in comp and "part" in comp:
            comp["text"] = comp.get("part")
    for branch in data.get("etymology", {}).get("branches", []):
        if isinstance(branch, dict):
            if "label" not in branch and "meaning_ja" in branch:
                branch["label"] = branch["meaning_ja"]
            branch.setdefault("label", "")
            branch.setdefault("meaning_en", "")
    if isinstance(data.get("etymology"), dict):
        data["etymology"].setdefault("language_chain", _pick_first_dict_list(scraped_data, "language_chain"))
        data["etymology"].setdefault("component_meanings", _pick_first_dict_list(scraped_data, "component_meanings"))
        data["etymology"].setdefault("etymology_variants", _pick_first_dict_list(scraped_data, "etymology_variants"))
        comps = data["etymology"].get("components", [])
        cm = data["etymology"].get("component_meanings", [])
        if isinstance(comps, list) and isinstance(cm, list):
            data["etymology"]["components"] = _merge_component_meanings_into_components(comps, cm)
    data["phonetic"] = repair_text(data.get("phonetic")) or _pick_first_str(scraped_data, "pronunciation_ipa")
    data["prompt_version"] = PROMPT_VERSION
    # Ensure every example_en contains the target word (LLM may omit it)
    w_lower = word.strip().lower()
    for idx, definition in enumerate(data.get("definitions", [])):
        if not isinstance(definition, dict):
            continue
        ex = definition.get("example_en")
        if not ex or not w_lower or w_lower not in (ex if isinstance(ex, str) else "").lower():
            definition["example_en"] = f"This is an example using {word} (sense {idx + 1})."
    _fill_empty_examples_with_gpt(word, data.get("definitions", []))
    return data


def _strip_json_code_fence(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[len("```json") :].strip()
    elif value.startswith("```"):
        value = value[len("```") :].strip()
    if value.endswith("```"):
        value = value[:-3].strip()
    return value


def _normalize_branch_items(branches: object) -> list[dict[str, str]]:
    if not isinstance(branches, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in branches:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        meaning_en = str(item.get("meaning_en", "")).strip()
        meaning_ja = str(item.get("meaning_ja", "")).strip()
        if not (label or meaning_en or meaning_ja):
            continue
        normalized.append({"label": label, "meaning_en": meaning_en, "meaning_ja": meaning_ja})
    return normalized


def enrich_core_image_and_branches(
    word_text: str,
    definitions: list[dict],
    etymology_data: dict,
) -> dict[str, Any] | None:
    if not settings.openai_api_key:
        return None
    prompt = load_prompt("etymology_enrichment.md")
    payload = {
        "target_word": word_text,
        "definitions": definitions or [],
        "etymology": etymology_data or {},
    }
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        text = _strip_json_code_fence(completion.output_text or "")
        data = repair_nested_strings(json.loads(text))
    except Exception:  # noqa: BLE001
        return None

    if not isinstance(data, dict):
        return None
    core_image = str(data.get("core_image", "")).strip()
    branches = _normalize_branch_items(data.get("branches"))
    if not core_image and not branches:
        return None
    return {"core_image": core_image, "branches": branches}


def translate_phrase_definitions(phrase_text: str, items: list[dict[str, str]]) -> list[dict[str, str]]:
    if not items:
        return []
    if not settings.openai_api_key:
        return [{"meaning_ja": "", "example_ja": ""} for _ in items]

    prompt = (
        "You are a bilingual dictionary assistant.\n"
        "Translate each entry into Japanese.\n"
        "Return strict JSON only in this shape:\n"
        '{"items":[{"meaning_ja":"...", "example_ja":"..."}]}\n'
        "Keep array length identical to input."
    )
    payload = {"phrase": phrase_text, "items": items}
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        raw = _strip_json_code_fence(completion.output_text or "")
        data = repair_nested_strings(json.loads(raw))
        out_items = data.get("items", []) if isinstance(data, dict) else []
        results: list[dict[str, str]] = []
        for idx in range(len(items)):
            row = out_items[idx] if idx < len(out_items) and isinstance(out_items[idx], dict) else {}
            results.append(
                {
                    "meaning_ja": str(row.get("meaning_ja", "")).strip(),
                    "example_ja": str(row.get("example_ja", "")).strip(),
                }
            )
        return results
    except Exception:  # noqa: BLE001
        return [{"meaning_ja": "", "example_ja": ""} for _ in items]
