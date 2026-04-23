import { Card, Muted, Stack } from "./atom";
import { WordLinkRow } from "./WordLinkRow";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Phrase } from "../types";

interface PhraseWiktionaryRelationsProps {
  phrase: Phrase;
}

const SECTIONS: { label: string; items: (phrase: Phrase) => string[] }[] = [
  { label: "類義語", items: (p) => p.wiktionary_synonyms ?? [] },
  { label: "対義語", items: (p) => p.wiktionary_antonyms ?? [] },
  { label: "参照", items: (p) => p.wiktionary_see_also ?? [] },
  { label: "派生語", items: (p) => p.wiktionary_derived_terms ?? [] },
  { label: "成句・慣用句", items: (p) => p.wiktionary_phrases ?? [] },
];

export function PhraseWiktionaryRelations({ phrase }: PhraseWiktionaryRelationsProps) {
  const groups = SECTIONS.map((s) => ({ label: s.label, items: s.items(phrase) }));

  return (
    <Card>
      <h3>関連語</h3>
      <Stack>
        {groups.map((group) => (
          <Card key={group.label} variant="sub" stack>
            <strong>{group.label}</strong>
            {group.items.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
            {group.items.map((text, idx) => (
              <Card key={`${group.label}-${idx}-${text}`} variant="sub" stack>
                <WordLinkRow value={text} linkedWordId={null} status="未登録" />
              </Card>
            ))}
          </Card>
        ))}
      </Stack>
    </Card>
  );
}
