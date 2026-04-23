import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { PhraseCard } from "../components/PhraseCard";
import { Card, Muted } from "../components/atom";
import { phraseApi } from "../lib/api";

type PhraseSortBy = "updated_at" | "created_at" | "text";
type SortOrder = "desc" | "asc";

const SORT_BY_OPTIONS: Array<{ value: PhraseSortBy; label: string }> = [
  { value: "updated_at", label: "最終更新日" },
  { value: "created_at", label: "追加日時" },
  { value: "text", label: "アルファベット順" },
];

const SORT_ORDER_OPTIONS: Array<{ value: SortOrder; label: string }> = [
  { value: "desc", label: "降順" },
  { value: "asc", label: "昇順" },
];

export function PhraseListPage() {
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<PhraseSortBy>("updated_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [deletingPhraseId, setDeletingPhraseId] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const phrasesQuery = useInfiniteQuery({
    queryKey: ["phrases", query, sortBy, sortOrder],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      phraseApi.list({
        q: query.trim(),
        sort_by: sortBy,
        sort_order: sortOrder,
        page: Number(pageParam),
        page_size: 20,
      }),
    getNextPageParam: (lastPage, allPages) => (lastPage.length === 20 ? allPages.length + 1 : undefined),
  });

  const phrases = useMemo(() => phrasesQuery.data?.pages.flatMap((page) => page) ?? [], [phrasesQuery.data]);
  const deleteMutation = useMutation({
    mutationFn: (phraseId: number) => phraseApi.delete(phraseId),
    onMutate: (phraseId) => setDeletingPhraseId(phraseId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["phrases"] });
    },
    onSettled: () => setDeletingPhraseId(null),
  });

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;
        if (!phrasesQuery.hasNextPage || phrasesQuery.isFetchingNextPage) return;
        void phrasesQuery.fetchNextPage();
      },
      { rootMargin: "200px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [phrasesQuery.fetchNextPage, phrasesQuery.hasNextPage, phrasesQuery.isFetchingNextPage]);

  return (
    <main className="container">
      <div className="page-header">
        <h1>熟語一覧</h1>
      </div>
      <Card stack>
        <label>
          <small>熟語検索</small>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="熟語を入力"
          />
        </label>
      </Card>
      <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ minWidth: 200 }}>
          <small>並び替え項目</small>
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value as PhraseSortBy)}>
            {SORT_BY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ minWidth: 140 }}>
          <small>順序</small>
          <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as SortOrder)}>
            {SORT_ORDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {phrasesQuery.isLoading && <Muted as="p">熟語を読み込み中...</Muted>}
      {!phrasesQuery.isLoading && phrases.length === 0 && <Muted as="p">熟語はまだありません。</Muted>}

      <section className="grid">
        {phrases.map((phrase) => (
          <PhraseCard
            key={phrase.id}
            phrase={phrase}
            deleting={deleteMutation.isPending && deletingPhraseId === phrase.id}
            onDelete={(phraseId) => deleteMutation.mutate(phraseId)}
          />
        ))}
      </section>

      {!phrasesQuery.isLoading && <div ref={loadMoreRef} style={{ height: 1 }} />}
      {phrasesQuery.isFetchingNextPage && <Muted as="p">さらに読み込み中...</Muted>}
    </main>
  );
}
