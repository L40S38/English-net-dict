import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Card, Muted, Row, Stack } from "../components/atom";
import { groupApi } from "../lib/api";

export function GroupListPage() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [query, setQuery] = useState("");
  const queryClient = useQueryClient();

  const groupsQuery = useQuery({
    queryKey: ["groups", query],
    queryFn: () => groupApi.list({ q: query.trim(), page: 1, page_size: 50 }),
  });

  const createMutation = useMutation({
    mutationFn: () => groupApi.create({ name, description }),
    onSuccess: async () => {
      setName("");
      setDescription("");
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (groupId: number) => groupApi.delete(groupId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const groups = groupsQuery.data?.items ?? [];

  return (
    <main className="container">
      <div className="page-header">
        <h1>単語/熟語グループ</h1>
      </div>

      <Card stack>
        <h3>新規グループ作成</h3>
        <label>
          <small>グループ名</small>
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="例: 挨拶系" />
        </label>
        <label>
          <small>説明</small>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="用途や分類ルールを記入"
            rows={3}
          />
        </label>
        <Row>
          <button
            type="button"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !name.trim()}
          >
            {createMutation.isPending ? "作成中..." : "作成"}
          </button>
        </Row>
      </Card>

      <Card stack>
        <label>
          <small>グループ検索</small>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="グループ名で絞り込み"
          />
        </label>
      </Card>

      {groupsQuery.isLoading && <Muted as="p">グループを読み込み中...</Muted>}
      {!groupsQuery.isLoading && groups.length === 0 && <Muted as="p">グループはまだありません。</Muted>}

      <section className="grid">
        {groups.map((group) => (
          <Card key={group.id} stack>
            <Link to={`/groups/${group.id}`}>{group.name}</Link>
            {group.description && <Muted as="p">{group.description}</Muted>}
            <Muted as="p">登録数: {group.item_count}</Muted>
            <Stack gap="sm">
              <button
                type="button"
                className="modal-cancel"
                onClick={() => {
                  const ok = window.confirm(`グループ「${group.name}」を削除しますか？`);
                  if (!ok) return;
                  deleteMutation.mutate(group.id);
                }}
                disabled={deleteMutation.isPending}
              >
                削除
              </button>
            </Stack>
          </Card>
        ))}
      </section>
    </main>
  );
}
