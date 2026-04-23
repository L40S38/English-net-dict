from __future__ import annotations

from core.models import Word
from core.services.gpt_service import _fill_empty_examples_with_gpt
from database_build.reporting import FieldDiff


def regenerate_examples_for_word(word: Word) -> list[FieldDiff]:
    definitions = list(word.definitions or [])
    if not definitions:
        return []
    definition_payloads = [
        {
            "part_of_speech": definition.part_of_speech,
            "meaning_en": definition.meaning_en,
            "example_en": definition.example_en,
        }
        for definition in definitions
    ]
    _fill_empty_examples_with_gpt(word.word, definition_payloads)
    diffs: list[FieldDiff] = []
    for definition, payload in zip(definitions, definition_payloads, strict=False):
        before = definition.example_en or ""
        after = str(payload.get("example_en", "")).strip()
        if after and after != before:
            definition.example_en = after
            diffs.append(
                FieldDiff(
                    name=f"definition[{definition.sort_order}].example_en",
                    before=before,
                    after=after,
                )
            )
    return diffs
