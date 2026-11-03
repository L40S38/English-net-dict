import { Link } from "react-router-dom";

import { Card, Chip, ChipList, Muted, Row, Stack } from "./atom";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Word } from "../types";

interface EtymologyMapProps {
  word: Word;
}

export function EtymologyMap({ word }: EtymologyMapProps) {
  const ety = word.etymology;
  const hasComponents = (ety?.components?.length ?? 0) > 0;
  const hasBranches = (ety?.branches?.length ?? 0) > 0;
  const hasRawDescription = Boolean(ety?.raw_description?.trim());
  const hasLanguageChain = (ety?.language_chain?.length ?? 0) > 0;

  return (
    <Card>
      <h3>語源マップ</h3>
      {!ety ? (
        <Muted as="p">{EMPTY_MESSAGES.noDataYet}</Muted>
      ) : (
        <Stack>
          <Card variant="sub" stack>
            <strong>コアイメージ（語源の核心）</strong>
            <p>{ety.core_image || "-"}</p>
            <Muted as="p">
              {ety.origin_language || ""} {ety.origin_word || ""}
            </Muted>
          </Card>
          <Card variant="sub" stack>
            <strong>意味の分岐</strong>
            <Muted as="p">コアイメージから派生した意味の広がりです。</Muted>
            <Stack>
              {hasBranches ? (
                ety.branches.map((branch, idx) => (
                  <Row key={idx} justify="between">
                    <span>{branch.label || `branch-${idx + 1}`}</span>
                    <Muted>{branch.meaning_en ?? ""}</Muted>
                  </Row>
                ))
              ) : (
                <Muted as="p">{EMPTY_MESSAGES.noDataYet}</Muted>
              )}
            </Stack>
          </Card>
          <Card variant="sub" stack>
            <strong>語源分解</strong>
            <Muted as="p">語の部品（接頭辞/語根など）を、意味ごとに分けて表示します。</Muted>
            <ChipList>
              {hasComponents ? (
                ety.components.map((component, idx) => {
                  const generic = new Set(["語根要素", "接頭要素", "語源要素"]);
                  const normalized = component.text.trim().toLowerCase();
                  const mappedMeaning =
                    (ety.component_meanings ?? []).find(
                      (item) =>
                        item.text.trim().toLowerCase() === normalized &&
                        item.meaning.trim() &&
                        !generic.has(item.meaning.trim()),
                    )?.meaning ?? component.meaning;
                  const etymologyPath = `/etymology-components/${encodeURIComponent(component.text)}?meaning=${encodeURIComponent(mappedMeaning)}&from=${encodeURIComponent(word.word)}`;
                  const wordPath = component.linked_word_id
                    ? `/words/${component.linked_word_id}`
                    : `/words/${encodeURIComponent(component.text)}`;
                  const hasWordMode =
                    component.candidate_word || (component.auto_modes ?? []).includes("word");
                  const displayMode = component.display_mode ?? "auto";
                  // auto指定時は、リンク可能な単語候補がある場合のみ単語リンクを優先表示する。
                  const effectiveMode =
                    displayMode === "auto" ? (hasWordMode ? "word" : "morpheme") : displayMode;
                  const chipLabel = `${component.text} : ${mappedMeaning}`;
                  const nodes = [];
                  if (effectiveMode === "word" || effectiveMode === "both") {
                    nodes.push(
                      <Link key={`${component.text}-${idx}-word`} to={wordPath}>
                        <Chip>{chipLabel} (単語)</Chip>
                      </Link>,
                    );
                  }
                  if (effectiveMode === "morpheme" || effectiveMode === "both") {
                    const morphemeChipText = generic.has((mappedMeaning ?? "").trim())
                      ? chipLabel
                      : `${chipLabel} (語源要素)`;
                    nodes.push(
                      <Link key={`${component.text}-${idx}-morpheme`} to={etymologyPath}>
                        <Chip>{morphemeChipText}</Chip>
                      </Link>,
                    );
                  }
                  return nodes;
                })
              ) : (
                <Muted as="p">{EMPTY_MESSAGES.noDataYet}</Muted>
              )}
            </ChipList>
          </Card>
          {(hasRawDescription || hasLanguageChain) && (
            <Card variant="sub" stack>
              <strong>語源</strong>
              {hasRawDescription ? (
                <p>{ety.raw_description}</p>
              ) : (
                <Muted as="p">{EMPTY_MESSAGES.noDataYet}</Muted>
              )}
              {hasLanguageChain && (
                <>
                  <Muted as="p">語源の来歴</Muted>
                  <p>
                    {(ety.language_chain ?? [])
                      .map((item) => `${item.lang_name || item.lang} ${item.word}`.trim())
                      .join(" → ")}
                  </p>
                </>
              )}
            </Card>
          )}
        </Stack>
      )}
    </Card>
  );
}
