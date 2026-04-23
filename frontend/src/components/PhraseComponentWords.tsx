import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Card, Muted } from "./atom";
import { WordCard } from "./WordCard";
import { wordApi } from "../lib/api";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Phrase } from "../types";

interface PhraseComponentWordsProps {
  phrase: Phrase;
}

export function PhraseComponentWords({ phrase }: PhraseComponentWordsProps) {
  const [deletingWordId, setDeletingWordId] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const words = phrase.words ?? [];
  const wordQueries = useQueries({
    queries: words.map((word) => ({
      queryKey: ["word", word.id],
      queryFn: () => wordApi.get(word.id),
      enabled: word.id > 0,
    })),
  });
  const detailWords = wordQueries.map((query) => query.data).filter((item) => item !== undefined);
  const isLoadingDetail = wordQueries.some((query) => query.isLoading);

  const deleteWordMutation = useMutation({
    mutationFn: (wordId: number) => wordApi.delete(wordId),
    onMutate: (wordId) => {
      setDeletingWordId(wordId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
      await queryClient.invalidateQueries({ queryKey: ["phrases"] });
      await queryClient.invalidateQueries({ queryKey: ["phrase", phrase.id] });
    },
    onSettled: () => {
      setDeletingWordId(null);
    },
  });

  return (
    <Card stack>
      <h3>構成語</h3>
      {words.length === 0 && <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>}
      {isLoadingDetail && <Muted as="p">構成語の詳細を読み込み中...</Muted>}
      {!isLoadingDetail && detailWords.length === 0 && words.length > 0 && (
        <Muted as="p">{EMPTY_MESSAGES.noData}</Muted>
      )}
      <section className="grid">
        {detailWords.map((word) => (
          <WordCard
            key={word.id}
            word={word}
            deleting={deleteWordMutation.isPending && deletingWordId === word.id}
            onDelete={(wordId) => deleteWordMutation.mutate(wordId)}
          />
        ))}
      </section>
    </Card>
  );
}
