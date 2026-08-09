import { useQueryClient } from "@tanstack/react-query";

import { AudioPlayButton } from "./AudioPlayButton";
import { Card, Muted, Row, Stack } from "./atom";
import { phraseApi } from "../lib/api";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Phrase } from "../types";

interface PhraseDefinitionsProps {
  phrase: Phrase;
}

export function PhraseDefinitions({ phrase }: PhraseDefinitionsProps) {
  const queryClient = useQueryClient();
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
                <Row>
                  <p>
                    <em>{item.example_en}</em>
                  </p>
                  <AudioPlayButton
                    audioPath={item.audio_path}
                    onGenerate={async () => {
                      const updated = await phraseApi.generateDefinitionAudio(phrase.id, item.id);
                      await queryClient.invalidateQueries({ queryKey: ["phrase", phrase.id] });
                      return updated;
                    }}
                  />
                </Row>
              </>
            )}
            {item.example_ja && <Muted as="p">{item.example_ja}</Muted>}
          </Card>
        ))}
      </Stack>
    </Card>
  );
}
