import { useQueryClient } from "@tanstack/react-query";

import { AudioPlayButton } from "./AudioPlayButton";
import { Card, Muted, Row, Stack } from "./atom";
import { wordApi } from "../lib/api";
import { POS_OPTIONS } from "../lib/constants";
import type { Word } from "../types";

interface WordDefinitionsProps {
  word: Word;
}

export function WordDefinitions({ word }: WordDefinitionsProps) {
  const queryClient = useQueryClient();
  const grouped = new Map<string, Word["definitions"]>();
  for (const def of word.definitions) {
    const key = def.part_of_speech || "その他";
    const bucket = grouped.get(key);
    if (bucket) {
      bucket.push(def);
    } else {
      grouped.set(key, [def]);
    }
  }
  const posOrder: string[] = POS_OPTIONS.map((item) => item.value);
  const sortedGroups = [...grouped.entries()].sort((a, b) => {
    const ai = posOrder.indexOf(a[0]);
    const bi = posOrder.indexOf(b[0]);
    if (ai !== -1 || bi !== -1) {
      if (ai === -1) return 1;
      if (bi === -1) return -1;
      return ai - bi;
    }
    return a[0].localeCompare(b[0]);
  });

  return (
    <Card>
      <h3>意味・例文</h3>
      <Stack>
        {sortedGroups.map(([partOfSpeech, defs]) => {
          const sortedDefs = [...defs].sort((a, b) => a.sort_order - b.sort_order);
          return (
            <Card key={partOfSpeech} as="article" variant="sub" stack>
              <strong>{partOfSpeech}</strong>
              <Stack>
                {sortedDefs.map((def, index) => (
                  <div key={def.id}>
                    <p>
                      {index + 1}. {def.meaning_en}
                    </p>
                    {def.meaning_ja && <Muted as="p">{def.meaning_ja}</Muted>}
                    <Muted as="p">例文)</Muted>
                    {(def.examples || []).map((example, exampleIndex) => (
                      <div key={`${def.id}-${exampleIndex}`}>
                        <Row>
                          <p>
                            <em>{example.example_en}</em>
                          </p>
                          {example.id != null && (
                            <AudioPlayButton
                              audioPath={example.audio_path}
                              onGenerate={async () => {
                                const updated = await wordApi.generateExampleAudio(
                                  word.id,
                                  example.id!,
                                );
                                await queryClient.invalidateQueries({ queryKey: ["word"] });
                                return updated;
                              }}
                            />
                          )}
                        </Row>
                        {example.example_ja && <Muted as="p">{example.example_ja}</Muted>}
                      </div>
                    ))}
                  </div>
                ))}
              </Stack>
            </Card>
          );
        })}
      </Stack>
    </Card>
  );
}
