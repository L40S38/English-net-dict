from __future__ import annotations

import asyncio
import json
from typing import Literal

from openai import AsyncOpenAI

from core.config import settings
from core.services import gpt_service as g
from core.services.example_cache import get_cached_example, make_cache_key, save_cached_example
from core.utils.text_repair import repair_nested_strings

ExampleMode = Literal["sequential", "parallel_thread", "parallel_async"]


async def _fill_empty_examples_with_mode(
    word: str,
    definitions: list[dict],
    *,
    example_mode: ExampleMode,
) -> None:
    if example_mode == "sequential":
        g._fill_empty_examples_with_gpt(word, definitions)
        return
    if not settings.openai_api_key or not word or not definitions:
        return

    need_list: list[tuple[int, dict]] = [
        (i, d)
        for i, d in enumerate(definitions)
        if isinstance(d, dict) and g._is_placeholder_example(d.get("example_en", ""), word)
    ]
    if not need_list:
        return

    prompt = g.load_prompt("example_sentence.md")
    model = settings.openai_model_structured
    w_lower = word.strip().lower()

    if example_mode == "parallel_thread":
        async def _run_one(idx: int, definition: dict) -> None:
            payload = {
                "target_word": word,
                "definitions": [
                    {
                        "meaning_en": definition.get("meaning_en", ""),
                        "part_of_speech": definition.get("part_of_speech", ""),
                    }
                ],
            }
            user_content = json.dumps(payload, ensure_ascii=False)
            cache_key = make_cache_key(prompt, model, user_content)
            cached = get_cached_example(cache_key)
            if cached and (not w_lower or w_lower in cached.lower()):
                definitions[idx]["example_en"] = cached
                return
            client = g.OpenAI(api_key=settings.openai_api_key)
            try:
                completion = await asyncio.to_thread(
                    client.responses.create,
                    model=model,
                    temperature=0.0,
                    input=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_content},
                    ],
                )
                ex = g._parse_single_example_response(completion.output_text or "")
                if ex and w_lower in ex.lower():
                    definitions[idx]["example_en"] = ex
                    save_cached_example(cache_key, ex)
            except Exception:  # noqa: BLE001
                return

        await asyncio.gather(*[_run_one(i, d) for i, d in need_list])
        return

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def _run_one_async(idx: int, definition: dict) -> None:
        payload = {
            "target_word": word,
            "definitions": [
                {
                    "meaning_en": definition.get("meaning_en", ""),
                    "part_of_speech": definition.get("part_of_speech", ""),
                }
            ],
        }
        user_content = json.dumps(payload, ensure_ascii=False)
        cache_key = make_cache_key(prompt, model, user_content)
        cached = get_cached_example(cache_key)
        if cached and (not w_lower or w_lower in cached.lower()):
            definitions[idx]["example_en"] = cached
            return
        try:
            completion = await client.responses.create(
                model=model,
                temperature=0.0,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            ex = g._parse_single_example_response(completion.output_text or "")
            if ex and w_lower in ex.lower():
                definitions[idx]["example_en"] = ex
                save_cached_example(cache_key, ex)
        except Exception:  # noqa: BLE001
            return

    await asyncio.gather(*[_run_one_async(i, d) for i, d in need_list])


async def generate_structured_word_data_async(
    word: str,
    wordnet_data: dict,
    scraped_data: list[dict],
    *,
    example_mode: ExampleMode = "parallel_async",
) -> dict:
    # region agent log
    from core.utils.dbg_log import dbg as _dbg
    # endregion
    if not settings.openai_api_key:
        # region agent log
        _dbg(
            "gpt_service_parallel.py:generate_structured_word_data_async",
            "no_api_key -> fallback",
            {"word": word},
            hypothesis_id="E",
        )
        # endregion
        return g._fallback_structured(word, wordnet_data, scraped_data)

    prompt = g.load_prompt("word_structuring.md")
    payload = {
        "target_word": word,
        "wordnet_data": wordnet_data,
        "scraped_data": scraped_data,
        "prompt_version": g.PROMPT_VERSION,
    }
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        completion = await client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        text = g._strip_json_code_fence(completion.output_text or "")
        data = repair_nested_strings(json.loads(text))
    except Exception as exc:  # noqa: BLE001
        # region agent log
        _dbg(
            "gpt_service_parallel.py:generate_structured_word_data_async",
            "exception -> fallback",
            {"word": word, "error_type": type(exc).__name__, "error": str(exc)[:300]},
            hypothesis_id="E",
        )
        # endregion
        return g._fallback_structured(word, wordnet_data, scraped_data)

    data.setdefault("forms", {})
    if not isinstance(data["forms"], dict):
        data["forms"] = {}
    scraped_forms = g._pick_forms(scraped_data)
    for key, value in scraped_forms.items():
        data["forms"].setdefault(key, value)
    normalized_data_phrases = g._normalize_phrase_entries(data["forms"].get("phrases"))
    scraped_phrases = g._pick_first_list(scraped_data, "phrases")
    if normalized_data_phrases:
        data["forms"]["phrases"] = normalized_data_phrases
    elif scraped_phrases:
        data["forms"]["phrases"] = g._phrase_entries_from_strings(scraped_phrases)

    for definition in data.get("definitions", []):
        definition["part_of_speech"] = g.normalize_part_of_speech(definition.get("part_of_speech"))
    for derivation in data.get("derivations", []):
        derivation["part_of_speech"] = g.normalize_part_of_speech(derivation.get("part_of_speech"))
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
        data["etymology"].setdefault("language_chain", g._pick_first_dict_list(scraped_data, "language_chain"))
        data["etymology"].setdefault("component_meanings", g._pick_first_dict_list(scraped_data, "component_meanings"))
        data["etymology"].setdefault("etymology_variants", g._pick_first_dict_list(scraped_data, "etymology_variants"))
        comps = data["etymology"].get("components", [])
        cm = data["etymology"].get("component_meanings", [])
        if isinstance(comps, list) and isinstance(cm, list):
            data["etymology"]["components"] = g._merge_component_meanings_into_components(comps, cm)
    data["phonetic"] = g.repair_text(data.get("phonetic")) or g._pick_first_str(scraped_data, "pronunciation_ipa")
    data["prompt_version"] = g.PROMPT_VERSION
    w_lower = word.strip().lower()
    for idx, definition in enumerate(data.get("definitions", [])):
        if not isinstance(definition, dict):
            continue
        ex = definition.get("example_en")
        if not ex or not w_lower or w_lower not in (ex if isinstance(ex, str) else "").lower():
            definition["example_en"] = f"This is an example using {word} (sense {idx + 1})."

    await _fill_empty_examples_with_mode(word, data.get("definitions", []), example_mode=example_mode)
    return data


async def enrich_core_image_and_branches_async(
    word_text: str,
    definitions: list[dict],
    etymology_data: dict,
) -> dict | None:
    if not settings.openai_api_key:
        return None
    prompt = g.load_prompt("etymology_enrichment.md")
    payload = {
        "target_word": word_text,
        "definitions": definitions or [],
        "etymology": etymology_data or {},
    }
    # region agent log
    from core.utils.dbg_log import dbg as _dbg
    # endregion
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        completion = await client.responses.create(
            model=settings.openai_model_structured,
            temperature=0.0,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        text = g._strip_json_code_fence(completion.output_text or "")
        data = repair_nested_strings(json.loads(text))
    except Exception as exc:  # noqa: BLE001
        # region agent log
        _dbg(
            "gpt_service_parallel.py:enrich_core_image_and_branches_async",
            "exception -> None",
            {"word": word_text, "error_type": type(exc).__name__, "error": str(exc)[:300]},
            hypothesis_id="B",
        )
        # endregion
        return None

    if not isinstance(data, dict):
        # region agent log
        _dbg(
            "gpt_service_parallel.py:enrich_core_image_and_branches_async",
            "non-dict response -> None",
            {"word": word_text, "data_type": type(data).__name__},
            hypothesis_id="B",
        )
        # endregion
        return None
    core_image = str(data.get("core_image", "")).strip()
    branches = g._normalize_branch_items(data.get("branches"))
    if not core_image and not branches:
        # region agent log
        _dbg(
            "gpt_service_parallel.py:enrich_core_image_and_branches_async",
            "empty result -> None",
            {"word": word_text},
            hypothesis_id="B",
        )
        # endregion
        return None
    return {"core_image": core_image, "branches": branches}
