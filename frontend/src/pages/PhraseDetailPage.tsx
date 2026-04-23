import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ImageViewer } from "../components/ImageViewer";
import { PageHeader } from "../components/PageHeader";
import { PhraseChatPanel } from "../components/PhraseChatPanel";
import { PhraseComponentWords } from "../components/PhraseComponentWords";
import { PhraseDefinitions } from "../components/PhraseDefinitions";
import { Muted } from "../components/atom";
import { phraseApi } from "../lib/api";

export function PhraseDetailPage() {
  const params = useParams();
  const phraseId = Number(params.phraseId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const phraseQuery = useQuery({
    queryKey: ["phrase", phraseId],
    queryFn: () => phraseApi.get(phraseId),
    enabled: Number.isFinite(phraseId) && phraseId > 0,
  });

  const enrichMutation = useMutation({
    mutationFn: () => phraseApi.enrich(phraseId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["phrase", phraseId] });
      await queryClient.invalidateQueries({ queryKey: ["phrases"] });
    },
  });

  const generateImageMutation = useMutation({
    mutationFn: (prompt?: string) => phraseApi.generateImage(phraseId, prompt),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["phrase", phraseId] });
    },
  });
  const deletePhraseMutation = useMutation({
    mutationFn: () => phraseApi.delete(phraseId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["phrases"] });
      navigate("/phrases");
    },
  });

  const phrase = phraseQuery.data;
  if (!phraseId || Number.isNaN(phraseId)) {
    return (
      <main className="container">
        <Muted as="p">熟語IDが不正です。</Muted>
      </main>
    );
  }

  return (
    <main className="container">
      <PageHeader
        title={phrase?.text ?? "熟語"}
        busy={
          phraseQuery.isLoading ||
          enrichMutation.isPending ||
          generateImageMutation.isPending ||
          deletePhraseMutation.isPending
        }
        actions={
          <>
            {phrase ? (
              <button type="button" onClick={() => enrichMutation.mutate()} disabled={enrichMutation.isPending}>
                {enrichMutation.isPending ? "再取得中..." : "データ再取得"}
              </button>
            ) : null}
            {phrase ? (
              <button
                type="button"
                onClick={() => {
                  const ok = window.confirm(`熟語「${phrase.text}」を削除しますか？`);
                  if (!ok) return;
                  deletePhraseMutation.mutate();
                }}
                disabled={deletePhraseMutation.isPending}
              >
                {deletePhraseMutation.isPending ? "削除中..." : "削除"}
              </button>
            ) : null}
            {phrase ? <Link to={`/phrases/${phrase.id}/edit`}>編集</Link> : null}
            <Link to="/phrases">一覧へ戻る</Link>
          </>
        }
      />
      {phrase?.meaning ? <Muted as="p">意味: {phrase.meaning}</Muted> : null}

      {phraseQuery.isLoading && <Muted as="p">熟語情報を読み込み中...</Muted>}
      {!phraseQuery.isLoading && !phrase && <Muted as="p">熟語が見つかりません。</Muted>}

      {phrase && (
        <div className="detail-layout">
          <div className="detail-main">
            <PhraseDefinitions phrase={phrase} />
            <PhraseComponentWords phrase={phrase} />
          </div>
          <aside className="detail-side">
            <ImageViewer
              title="イメージ画像"
              entityLabel={phrase.text}
              images={phrase.images ?? []}
              fetchDefaultPrompt={() => phraseApi.getDefaultImagePrompt(phrase.id)}
              onGenerate={(prompt) => generateImageMutation.mutateAsync(prompt)}
              loading={generateImageMutation.isPending}
            />
            <PhraseChatPanel phraseId={phrase.id} />
          </aside>
        </div>
      )}
    </main>
  );
}
