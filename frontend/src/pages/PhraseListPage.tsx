import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { Card, Muted, Stack } from "../components/atom";
import { phraseApi } from "../lib/api";

export function PhraseListPage() {
  const [query, setQuery] = useState("");
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const phrasesQuery = useInfiniteQuery({
    queryKey: ["phrases", query],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      phraseApi.list({
        q: query.trim(),
        page: Number(pageParam),
        page_size: 20,
      }),
    getNextPageParam: (lastPage, allPages) => (lastPage.length === 20 ? allPages.length + 1 : undefined),
  });

  const phrases = useMemo(() => phrasesQuery.data?.pages.flatMap((page) => page) ?? [], [phrasesQuery.data]);

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
      {phrasesQuery.isLoading && <Muted as="p">熟語を読み込み中...</Muted>}
      {!phrasesQuery.isLoading && phrases.length === 0 && <Muted as="p">熟語はまだありません。</Muted>}

      <section className="grid">
        {phrases.map((phrase) => (
          <Card key={phrase.id} stack>
            <Link to={`/phrases/${phrase.id}`}>{phrase.text}</Link>
            <Stack gap="sm">
              <Muted as="p">{phrase.meaning || "意味は未設定です。"}</Muted>
            </Stack>
          </Card>
        ))}
      </section>

      {!phrasesQuery.isLoading && <div ref={loadMoreRef} style={{ height: 1 }} />}
      {phrasesQuery.isFetchingNextPage && <Muted as="p">さらに読み込み中...</Muted>}
    </main>
  );
}
