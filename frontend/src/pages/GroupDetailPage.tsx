import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { GroupChatPanel } from "../components/GroupChatPanel";
import { GroupImageViewer } from "../components/GroupImageViewer";
import { PageHeader } from "../components/PageHeader";
import { Card, Muted, Row, Stack } from "../components/atom";
import { groupApi } from "../lib/api";

export function GroupDetailPage() {
  const params = useParams();
  const groupId = Number(params.groupId);
  const queryClient = useQueryClient();

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => groupApi.get(groupId),
    enabled: Number.isFinite(groupId) && groupId > 0,
  });

  const generateImageMutation = useMutation({
    mutationFn: (prompt?: string) => groupApi.generateImage(groupId, prompt),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
    },
  });

  const group = groupQuery.data;

  if (!groupId || Number.isNaN(groupId)) {
    return (
      <main className="container">
        <Muted as="p">グループIDが不正です。</Muted>
      </main>
    );
  }

  return (
    <main className="container">
      <PageHeader
        title={group?.name ?? "グループ"}
        busy={groupQuery.isLoading || generateImageMutation.isPending}
        actions={
          <>
            <Link to={`/groups/${groupId}/edit`}>編集</Link>
            <Link to="/groups">一覧へ戻る</Link>
          </>
        }
      />
      {group?.description && <Muted as="p">{group.description}</Muted>}

      {groupQuery.isLoading && <Muted as="p">グループ情報を読み込み中...</Muted>}
      {!groupQuery.isLoading && !group && <Muted as="p">グループが見つかりません。</Muted>}

      {group && (
        <div className="detail-layout">
          <div className="detail-main">
            <Card stack>
              <h3>登録済みアイテム</h3>
              {group.items.length === 0 && <Muted as="p">まだ追加されていません。</Muted>}
              {group.items.map((item) => (
                <Card key={item.id} variant="sub" stack>
                  {item.item_type === "word" && (
                    <Row>
                      <strong>単語</strong>
                      <span>{item.word}</span>
                    </Row>
                  )}
                  {item.item_type === "phrase" && (
                    <Stack gap="sm">
                      <strong>熟語</strong>
                      <Muted as="p">{item.phrase_text}</Muted>
                      {item.phrase_meaning && <Muted as="p">意味: {item.phrase_meaning}</Muted>}
                    </Stack>
                  )}
                  {item.item_type === "example" && (
                    <Stack gap="sm">
                      <strong>例文</strong>
                      <Muted as="p">{item.example_en}</Muted>
                      {item.example_ja && <Muted as="p">{item.example_ja}</Muted>}
                    </Stack>
                  )}
                </Card>
              ))}
            </Card>
          </div>
          <aside className="detail-side">
            <GroupImageViewer
              group={group}
              onGenerate={(prompt) => generateImageMutation.mutateAsync(prompt)}
              loading={generateImageMutation.isPending}
            />
            <GroupChatPanel groupId={group.id} />
          </aside>
        </div>
      )}
    </main>
  );
}
