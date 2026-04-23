import { Card, Muted, Stack } from "./atom";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Phrase } from "../types";

interface PhraseDefinitionsProps {
  phrase: Phrase;
}

export function PhraseDefinitions({ phrase }: PhraseDefinitionsProps) {
  const definitions = [...(phrase.definitions ?? [])].sort((a, b) => a.sort_order - b.sort_order);
  return (
    <Card stack>
      <h3>意味・例文</h3>
      {definitions.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
      <Stack>
        {definitions.map((item, idx) => (
          <Card key={item.id} variant="sub" stack>
            <strong>
              {item.part_of_speech || "phrase"} #{idx + 1}
            </strong>
            {item.meaning_ja && <p>{item.meaning_ja}</p>}
            {item.meaning_en && <Muted as="p">{item.meaning_en}</Muted>}
            {item.example_en && (
              <>
                <Muted as="p">例文</Muted>
                <p>
                  <em>{item.example_en}</em>
                </p>
              </>
            )}
            {item.example_ja && <Muted as="p">{item.example_ja}</Muted>}
          </Card>
        ))}
      </Stack>
    </Card>
  );
}
