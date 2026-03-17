import { Card, Muted, Stack } from "./atom";
import { WordLinkRow } from "./WordLinkRow";
import { EMPTY_MESSAGES, RELATION_TYPE_LABELS } from "../lib/constants";
import type { Word } from "../types";

interface Props {
  word: Word;
}

export function RelatedWords({ word }: Props) {
  const groups = (["synonym", "antonym", "confusable", "cognate"] as const).map((type) => ({
    type,
    items: word.related_words.filter((r) => r.relation_type === type),
  }));
  return (
    <Card>
      <h3>関連語</h3>
      <Stack>
        {groups.map((group) => (
          <Card key={group.type} variant="sub" stack>
            <strong>{RELATION_TYPE_LABELS[group.type]}</strong>
            {group.items.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
            {group.items.map((item) => (
              <Card key={item.id} variant="sub" stack>
                <WordLinkRow
                  value={item.related_word}
                  linkedWordId={item.linked_word_id}
                  secondary={item.note}
                  status={item.linked_word_id ? "登録済み" : "未登録"}
                />
              </Card>
            ))}
          </Card>
        ))}
      </Stack>
    </Card>
  );
}
