from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import core.services.gpt_service as gpt_service


class _FakeResponses:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = outputs
        self.call_count = 0

    def create(self, **kwargs: object) -> SimpleNamespace:
        idx = min(self.call_count, len(self._outputs) - 1)
        self.call_count += 1
        return SimpleNamespace(output_text=self._outputs[idx])


class _FakeClient:
    def __init__(self, outputs: list[str]) -> None:
        self.responses = _FakeResponses(outputs)


@pytest.fixture(autouse=True)
def _no_real_openai_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let these tests reach the real OpenAI API, even accidentally: force a
    dummy key (so generate_structured_word_data doesn't just skip to the fallback)
    and stub out the extra GPT call for filling in missing examples, which isn't
    what these tests are about."""
    monkeypatch.setattr(gpt_service.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(gpt_service, "_fill_empty_examples_with_gpt", lambda *a, **k: None)


def _patch_openai(monkeypatch: pytest.MonkeyPatch, outputs: list[str]) -> _FakeClient:
    client = _FakeClient(outputs)
    monkeypatch.setattr(gpt_service, "OpenAI", lambda api_key=None: client)
    return client


def test_generate_structured_word_data_recovers_pos_gpt_omitted_on_final_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: when GPT drops a whole part-of-speech's definitions and the
    mismatch persists into the final retry, the dropped POS must be recovered from
    curated_defs (the Wiktionary data sent to GPT) rather than silently vanishing -
    otherwise word_service._drop_forms_without_matching_pos later strips real
    inflection forms (e.g. past_tense) for that POS."""
    curated = [
        {
            "part_of_speech": "noun",
            "meaning_en": "the amount produced",
            "example_en": "",
            "examples_en": [],
            "sort_order": 0,
        },
        {
            "part_of_speech": "verb",
            "meaning_en": "to produce or manufacture",
            "example_en": "The factory outputs steel.",
            "examples_en": ["The factory outputs steel."],
            "sort_order": 1,
        },
    ]
    monkeypatch.setattr(gpt_service, "_curate_wiktionary_definitions_for_gpt", lambda scraped_data: curated)

    # GPT omits the verb definition on both attempts, so the mismatch persists and
    # the final (still-mismatched) result is accepted per the documented trade-off.
    gpt_noun_only = json.dumps(
        {
            "definitions": [
                {
                    "part_of_speech": "noun",
                    "meaning_en": "the amount produced",
                    "meaning_ja": "生産量",
                    "examples_en": [],
                    "examples_ja": [],
                    "sort_order": 0,
                }
            ],
        }
    )
    _patch_openai(monkeypatch, [gpt_noun_only, gpt_noun_only])

    result = gpt_service.generate_structured_word_data("output", {}, [])

    pos_set = {d["part_of_speech"] for d in result["definitions"]}
    assert "名詞 noun" in pos_set
    assert "動詞 verb" in pos_set  # recovered from curated_defs despite GPT omitting it
    recovered = next(d for d in result["definitions"] if d["part_of_speech"] == "動詞 verb")
    assert recovered["meaning_en"] == "to produce or manufacture"
    assert recovered["meaning_ja"] == ""  # no translation available - filled in later, not fabricated


def test_generate_structured_word_data_does_not_duplicate_pos_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curated = [
        {"part_of_speech": "noun", "meaning_en": "a thing", "example_en": "", "examples_en": [], "sort_order": 0},
    ]
    monkeypatch.setattr(gpt_service, "_curate_wiktionary_definitions_for_gpt", lambda scraped_data: curated)

    gpt_noun = json.dumps(
        {
            "definitions": [
                {
                    "part_of_speech": "noun",
                    "meaning_en": "a thing",
                    "meaning_ja": "もの",
                    "examples_en": [],
                    "examples_ja": [],
                    "sort_order": 0,
                }
            ],
        }
    )
    _patch_openai(monkeypatch, [gpt_noun])

    result = gpt_service.generate_structured_word_data("thing", {}, [])

    assert len(result["definitions"]) == 1


def test_generate_structured_word_data_falls_back_when_gpt_returns_non_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: a non-dict GPT response (e.g. a bare JSON array) used to be
    accepted as `data`, and the following `data.setdefault("forms", {})` raised
    AttributeError instead of falling back to the degraded structuring."""
    _patch_openai(monkeypatch, ["[]"])

    result = gpt_service.generate_structured_word_data("ghostword", {}, [])

    assert isinstance(result, dict)
    assert isinstance(result.get("definitions"), list)
    assert len(result["definitions"]) >= 1
