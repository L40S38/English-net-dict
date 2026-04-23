import { Link } from "react-router-dom";

import { Card, Muted, Stack } from "./atom";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Phrase } from "../types";

interface PhraseComponentWordsProps {
  phrase: Phrase;
}

export function PhraseComponentWords({ phrase }: PhraseComponentWordsProps) {
  const words = phrase.words ?? [];
  return (
    <Card stack>
      <h3>構成語</h3>
      {words.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
      <Stack>
        {words.map((word) => (
          <Card key={word.id} variant="sub" stack>
            <Link to={`/words/${word.id}`}>{word.word}</Link>
            {word.phonetic ? <Muted as="p">{word.phonetic}</Muted> : null}
          </Card>
        ))}
      </Stack>
    </Card>
  );
}
