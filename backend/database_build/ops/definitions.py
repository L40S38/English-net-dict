from __future__ import annotations

from core.models import DefinitionExample, Word
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
            "examples_en": [
                example.example_en for example in sorted(definition.examples, key=lambda x: (x.sort_order, x.id))
            ],
            "examples_ja": [
                example.example_ja for example in sorted(definition.examples, key=lambda x: (x.sort_order, x.id))
            ],
        }
        for definition in definitions
    ]
    _fill_empty_examples_with_gpt(word.word, definition_payloads)
    diffs: list[FieldDiff] = []
    for definition, payload in zip(definitions, definition_payloads, strict=False):
        before = (
            definition.examples[0].example_en if definition.examples else ""
        )
        examples_en = payload.get("examples_en")
        examples_ja = payload.get("examples_ja")
        after = str(examples_en[0] if isinstance(examples_en, list) and examples_en else "").strip()
        if after and after != before:
            after_ja = str(
                examples_ja[0] if isinstance(examples_ja, list) and examples_ja else ""
            ).strip()
            if definition.examples:
                # _fill_empty_examples_with_gpt only ever (re)generates the
                # primary (index 0) example; sort_order 1+ are left untouched.
                definition.examples[0].example_en = after
                if after_ja:
                    definition.examples[0].example_ja = after_ja
            else:
                # Previously this branch was skipped entirely, so a
                # definition with no existing example rows silently never
                # got the newly-generated one persisted despite being
                # reported as updated below.
                definition.examples.append(
                    DefinitionExample(example_en=after, example_ja=after_ja, sort_order=0)
                )
            diffs.append(
                FieldDiff(
                    name=f"definition[{definition.sort_order}].example_en",
                    before=before,
                    after=after,
                )
            )
    return diffs
