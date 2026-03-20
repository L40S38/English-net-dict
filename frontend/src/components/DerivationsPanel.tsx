import { Card, Muted, Stack } from "./atom";
import { WordLinkRow } from "./WordLinkRow";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { PhraseEntry, Word } from "../types";

interface Props {
  word: Word;
}

export function DerivationsPanel({ word }: Props) {
  const rawPhrases = (word.forms?.phrases ?? []) as unknown[];
  const phrases: PhraseEntry[] = rawPhrases.flatMap((item) => {
    if (typeof item === "string") {
      const phrase = item.trim();
      return phrase ? [{ phrase, meaning: "" }] : [];
    }
    if (!item || typeof item !== "object") {
      return [];
    }
    const phrase = String(
      (item as { phrase?: string; text?: string }).phrase ?? (item as { text?: string }).text ?? "",
    ).trim();
    if (!phrase) {
      return [];
    }
    const meaning = String(
      (item as { meaning?: string; meaning_en?: string; meaning_ja?: string }).meaning ??
        (item as { meaning_en?: string }).meaning_en ??
        (item as { meaning_ja?: string }).meaning_ja ??
        "",
    ).trim();
    return [{ phrase, meaning }];
  });
  return (
    <Card stack>
      <h3>派生語</h3>
      <Stack>
        <Card variant="sub" stack>
          <strong>単語</strong>
          {word.derivations.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
          {word.derivations.map((d) => (
            <Card key={d.id} variant="sub" stack>
              <WordLinkRow
                value={d.derived_word}
                linkedWordId={d.linked_word_id}
                secondary={`(${d.part_of_speech}) ${d.meaning_ja}`}
                status={d.linked_word_id ? "登録済み" : "未登録"}
              />
            </Card>
          ))}
        </Card>
        <Card variant="sub" stack>
          <strong>熟語</strong>
          {phrases.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
          {phrases.map((entry, idx) => (
            <Card key={`${entry.phrase}-${idx}`} variant="sub" stack>
              <WordLinkRow value={entry.phrase} secondary={entry.meaning} />
            </Card>
          ))}
        </Card>
      </Stack>
    </Card>
  );
}
