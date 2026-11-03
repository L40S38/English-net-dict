from __future__ import annotations

from core.services.scraper.wiktionary import WiktionaryScraper


def test_nested_subdef_example_is_not_leaked_into_parent_definition() -> None:
    """Regression test: a `##:` example line under a *real* (non-label-only) `#`
    definition's ignored `##` sub-definition used to get attached to the parent `#`
    definition instead of being dropped along with the ignored sub-definition."""
    wikitext = (
        "==English==\n"
        "\n"
        "===Verb===\n"
        "# to give up completely\n"
        "## a real sub-sense that should be ignored\n"
        "##: {{ux|en|This sub-sense example should not leak.}}\n"
        "# to yield or hand over\n"
        "#: {{ux|en|Real example for the second sense.}}\n"
    )

    definitions = WiktionaryScraper._extract_definitions_with_examples(wikitext)

    assert [d["meaning_en"] for d in definitions] == ["to give up completely", "to yield or hand over"]
    assert definitions[0]["example_en"] == ""
    assert definitions[1]["example_en"] == "Real example for the second sense."


def test_label_only_parent_still_recovers_nested_definition_and_its_example() -> None:
    """The original bug this nesting support was added for: a label-only `#` line
    (empty after stripping templates) followed by the real definition one level
    deeper as `##`, with its example as `##:` - both must still be picked up."""
    wikitext = (
        "==English==\n"
        "\n"
        "===Verb===\n"
        "# {{lb|en|transitive}}\n"
        "## to retain something\n"
        "##: {{ux|en|Example for the nested real definition.}}\n"
    )

    definitions = WiktionaryScraper._extract_definitions_with_examples(wikitext)

    assert [d["meaning_en"] for d in definitions] == ["to retain something"]
    assert definitions[0]["example_en"] == "Example for the nested real definition."
