import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Card, Muted, Row, Stack } from "../components/atom";
import { componentApi } from "../lib/api";

export function EtymologySearchPage() {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);

  const listQuery = useQuery({
    queryKey: ["etymology-components", query, page],
    queryFn: () => componentApi.list({ q: query.trim(), page, page_size: 20 }),
  });

  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const maxPage = Math.max(1, Math.ceil(total / 20));

  return (
    <main className="container">
      <div className="page-header">
        <h1>語源検索</h1>
      </div>
      <Card stack>
        <label>
          <small>語源要素を検索</small>
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="例: vert, mis, tion"
          />
        </label>
        <Muted as="p">登録済み語源要素のみ表示されます。</Muted>
      </Card>

      {listQuery.isLoading && <Muted as="p">語源要素を読み込み中...</Muted>}
      {!listQuery.isLoading && items.length === 0 && <Muted as="p">該当する語源要素はありません。</Muted>}

      <section className="grid">
        {items.map((item) => (
          <Card key={item.id} stack>
            <Link to={`/etymology-components/${encodeURIComponent(item.component_text)}`}>
              {item.component_text}
            </Link>
            {item.resolved_meaning && <Muted as="p">意味: {item.resolved_meaning}</Muted>}
            <Muted as="p">登録単語数: {item.word_count}</Muted>
          </Card>
        ))}
      </section>

      {total > 0 && (
        <Row>
          <button type="button" onClick={() => setPage((prev) => Math.max(1, prev - 1))} disabled={page <= 1}>
            前へ
          </button>
          <Stack gap="sm">
            <Muted as="span">
              {page} / {maxPage}
            </Muted>
          </Stack>
          <button
            type="button"
            onClick={() => setPage((prev) => Math.min(maxPage, prev + 1))}
            disabled={page >= maxPage}
          >
            次へ
          </button>
        </Row>
      )}
    </main>
  );
}
