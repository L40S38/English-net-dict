import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { GroupChatPanel } from "../components/GroupChatPanel";
import { ImageViewer } from "../components/ImageViewer";
import { PageHeader } from "../components/PageHeader";
import { Card, Muted, Row, Stack } from "../components/atom";
import { groupApi } from "../lib/api";
import type { WordGroupItem } from "../types";

function wordDetailPath(item: WordGroupItem): string | null {
  if (item.item_type === "word") {
    if (item.word_id != null) {
      return `/words/${item.word_id}`;
    }
    if (item.word) {
      return `/words/${encodeURIComponent(item.word)}`;
    }
    return null;
  }
  if (item.item_type === "example" && item.word_id != null) {
    return `/words/${item.word_id}`;
  }
  return null;
}

function phraseDetailPath(item: WordGroupItem): string | null {
  if (item.item_type === "phrase" && item.phrase_id != null) {
    return `/phrases/${item.phrase_id}`;
  }
  return null;
}

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
              {group.items.map((item) => {
                const wordHref = wordDetailPath(item);
                const phraseHref = phraseDetailPath(item);
                return (
                  <Card key={item.id} variant="sub" stack>
                    {item.item_type === "word" && (
                      <Row>
                        <strong>単語</strong>
                        {wordHref && item.word ? (
                          <Link to={wordHref}>{item.word}</Link>
                        ) : (
                          <span>{item.word}</span>
                        )}
                      </Row>
                    )}
                    {item.item_type === "phrase" && (
                      <Stack gap="sm">
                        <Row justify="between">
                          <Row>
                            <strong>熟語</strong>
                            <Muted as="span">{item.phrase_text}</Muted>
                          </Row>
                          {phraseHref ? (
                            <Link className="detail-link-button" to={phraseHref}>
                              詳細
                            </Link>
                          ) : null}
                        </Row>
                        {item.phrase_meaning && <Muted as="p">意味: {item.phrase_meaning}</Muted>}
                        {item.word_id != null ? (
                          <Muted as="p">
                            <Link to={`/words/${item.word_id}`}>構成語ページへ</Link>
                          </Muted>
                        ) : null}
                      </Stack>
                    )}
                    {item.item_type === "example" && (
                      <Stack gap="sm">
                        <Row>
                          <strong>例文</strong>
                          {wordHref ? (
                            <Link to={wordHref}>単語ページへ</Link>
                          ) : null}
                        </Row>
                        <Muted as="p">{item.example_en}</Muted>
                        {item.example_ja && <Muted as="p">{item.example_ja}</Muted>}
                      </Stack>
                    )}
                  </Card>
                );
              })}
            </Card>
          </div>
          <aside className="detail-side">
            <ImageViewer
              title="グループ画像"
              entityLabel={group.name}
              images={group.images}
              defaultPromptRows={5}
              fetchDefaultPrompt={() => groupApi.getDefaultImagePrompt(group.id)}
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
