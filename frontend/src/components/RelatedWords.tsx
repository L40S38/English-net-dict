import { Card, Muted, Stack } from "./atom";
import { PhraseRegisterAction } from "./PhraseRegisterAction";
import { WordLinkRow } from "./WordLinkRow";
import { EMPTY_MESSAGES, RELATION_TYPE_LABELS } from "../lib/constants";
import { hasMultipleWordTokens } from "../lib/tokenLinks";
import { usePhraseRegistration } from "../lib/usePhraseRegistration";
import type { Word } from "../types";

interface RelatedWordsProps {
  word: Word;
}

export function RelatedWords({ word }: RelatedWordsProps) {
  const groups = (["synonym", "antonym", "confusable", "cognate"] as const).map((type) => ({
    type,
    items: word.related_words.filter((r) => r.relation_type === type),
  }));
  // 関連語には複数単語からなる熟語（例: "work out"）が含まれることが多いため、
  // それらは熟語候補として登録/詳細アクションを共通フックで提供する。
  const phraseCandidateTexts = word.related_words
    .map((item) => item.related_word)
    .filter((text) => hasMultipleWordTokens(text));
  const { getPhraseId, registerPhrase, isRegistering, isMutating } =
    usePhraseRegistration(phraseCandidateTexts);

  return (
    <Card>
      <h3>関連語</h3>
      <Stack>
        {groups.map((group) => (
          <Card key={group.type} variant="sub" stack>
            <strong>{RELATION_TYPE_LABELS[group.type]}</strong>
            {group.items.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
            {group.items.map((item) => {
              const isPhraseCandidate = hasMultipleWordTokens(item.related_word);
              return (
                <Card key={item.id} variant="sub" stack>
                  <WordLinkRow
                    value={item.related_word}
                    linkedWordId={item.linked_word_id}
                    secondary={item.note}
                    status={item.linked_word_id ? "登録済み" : "未登録"}
                    trailing={
                      isPhraseCandidate ? (
                        <PhraseRegisterAction
                          text={item.related_word}
                          phraseId={getPhraseId(item.related_word)}
                          pending={isRegistering(item.related_word)}
                          disabled={isMutating}
                          onRegister={registerPhrase}
                        />
                      ) : undefined
                    }
                  />
                </Card>
              );
            })}
          </Card>
        ))}
      </Stack>
    </Card>
  );
}
