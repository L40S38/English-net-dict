import { Link } from "react-router-dom";

import { Card, Muted, Stack } from "./atom";
import { WordLinkRow } from "./WordLinkRow";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Word } from "../types";

interface DerivationsPanelProps {
  word: Word;
}

export function DerivationsPanel({ word }: DerivationsPanelProps) {
  const phrases = word.phrases ?? [];
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
          {phrases.map((entry) => (
            <Card key={entry.id} variant="sub" stack>
              <WordLinkRow
                value={entry.text}
                secondary={entry.meaning}
                disableValueLink
                trailing={
                  <Link className="detail-link-button" to={`/phrases/${entry.id}`}>
                    詳細
                  </Link>
                }
              />
            </Card>
          ))}
        </Card>
      </Stack>
    </Card>
  );
}
