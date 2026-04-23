import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Card, Field, Muted, Row, Stack } from "../atom";
import { wordApi } from "../../lib/api";
import type { WordSummary } from "../../types";

interface PhraseEditWordsTabProps {
  words: WordSummary[];
  setWords: (next: WordSummary[]) => void;
}

export function PhraseEditWordsTab({ words, setWords }: PhraseEditWordsTabProps) {
  const [q, setQ] = useState("");
  const suggestionsQuery = useQuery({
    queryKey: ["word-suggest", q],
    queryFn: () => wordApi.suggest(q, 10),
    enabled: q.trim().length > 0,
  });
  const candidates = useMemo(() => suggestionsQuery.data ?? [], [suggestionsQuery.data]);

  const addWord = async (wordText: string) => {
    const result = await wordApi.list({ q: wordText, page: 1, page_size: 10 });
    const exact = result.items.find((item) => item.word.toLowerCase() === wordText.toLowerCase());
    if (!exact) return;
    if (words.some((item) => item.id === exact.id)) return;
    setWords([...words, { id: exact.id, word: exact.word, phonetic: exact.phonetic }]);
    setQ("");
  };

  return (
    <Stack>
      <Field label="登録済み単語を検索">
        <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="単語を入力" />
      </Field>
      {candidates.length > 0 && (
        <Card stack variant="sub">
          {candidates.map((candidate) => (
            <Row key={candidate} justify="between">
              <span>{candidate}</span>
              <button type="button" onClick={() => void addWord(candidate)}>
                追加
              </button>
            </Row>
          ))}
        </Card>
      )}
      <Card stack>
        <h4>紐づけ済み構成語</h4>
        {words.length === 0 && <Muted as="p">まだありません。</Muted>}
        {words.map((word) => (
          <Row key={word.id} justify="between">
            <span>{word.word}</span>
            <button
              type="button"
              className="modal-cancel"
              onClick={() => setWords(words.filter((item) => item.id !== word.id))}
            >
              削除
            </button>
          </Row>
        ))}
      </Card>
    </Stack>
  );
}
