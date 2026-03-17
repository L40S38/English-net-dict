import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DerivationsPanel } from "../components/DerivationsPanel";
import { EtymologyMap } from "../components/EtymologyMap";
import { ImageViewer } from "../components/ImageViewer";
import { PageHeader } from "../components/PageHeader";
import { ConfirmModal } from "../components/ConfirmModal";
import { RelatedWords } from "../components/RelatedWords";
import { WordCard } from "../components/WordCard";
import { WordChatPanel } from "../components/WordChatPanel";
import { WordDefinitions } from "../components/WordDefinitions";
import { Card, Muted, Row } from "../components/atom";
import { wordApi } from "../lib/api";
import { EMPTY_MESSAGES } from "../lib/constants";

function isPhrase(text: string): boolean {
  return text
    .trim()
    .split(/\s+/)
    .filter(Boolean).length >= 2;
}

export function WordDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const rawWordKey = (params.wordKey ?? "").trim();
  // wordKey は `/words/123` のような ID と `/words/abandon` のような文字列の両方を受ける。
  // 数値なら get(id) で取得し、文字列なら getByWord(word) で取得する。
  const numericWordId = /^\d+$/.test(rawWordKey) ? Number(rawWordKey) : null;
  const queryClient = useQueryClient();

  const wordQuery = useQuery({
    queryKey: ["word", rawWordKey],
    queryFn: () =>
      numericWordId !== null ? wordApi.get(numericWordId) : wordApi.getByWord(rawWordKey),
    enabled: rawWordKey.length > 0,
    retry: false,
  });

  const registerMutation = useMutation({
    mutationFn: () => wordApi.create(rawWordKey),
    onSuccess: (createdWords) => {
      const first = createdWords[0];
      if (!first) {
        return;
      }
      navigate(`/words/${first.id}`, { replace: true });
    },
  });

  const generateImageMutation = useMutation({
    mutationFn: (prompt?: string) => wordApi.generateImage(wordQuery.data!.id, prompt),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["word", rawWordKey] });
    },
  });

  const rescrapeMutation = useMutation({
    mutationFn: () => wordApi.rescrape(wordQuery.data!.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["word", rawWordKey] });
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
  });
  const deleteWordMutation = useMutation({
    mutationFn: () => wordApi.delete(wordQuery.data!.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
      navigate("/");
    },
  });

  const word = wordQuery.data;
  const isBusy =
    wordQuery.isLoading ||
    rescrapeMutation.isPending ||
    generateImageMutation.isPending ||
    deleteWordMutation.isPending;
  const forms = word?.forms ?? {};
  const formEntries = [
    ["三単現", String(forms.third_person_singular ?? "")],
    ["現在分詞", String(forms.present_participle ?? "")],
    ["過去形", String(forms.past_tense ?? "")],
    ["過去分詞", String(forms.past_participle ?? "")],
    ["複数形", String(forms.plural ?? "")],
    ["比較級", String(forms.comparative ?? "")],
    ["最上級", String(forms.superlative ?? "")],
    ["可算/不可算", forms.uncountable ? "不可算あり" : ""],
  ].filter(([, value]) => value);

  const isNotFound =
    wordQuery.isError &&
    axios.isAxiosError(wordQuery.error) &&
    wordQuery.error.response?.status === 404;

  const [deletingWordId, setDeletingWordId] = useState<number | null>(null);
  const [showPhraseConfirm, setShowPhraseConfirm] = useState(false);
  const partialMatchQuery = useQuery({
    queryKey: ["words", "partial", rawWordKey],
    queryFn: () => wordApi.list({ q: rawWordKey, page_size: 20 }),
    enabled: rawWordKey.length > 0 && numericWordId === null && isNotFound,
  });
  const deleteFromListMutation = useMutation({
    mutationFn: (wordId: number) => wordApi.delete(wordId),
    onMutate: (wordId) => setDeletingWordId(wordId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
      await queryClient.invalidateQueries({ queryKey: ["words", "partial", rawWordKey] });
    },
    onSettled: () => setDeletingWordId(null),
  });

  if (isNotFound && numericWordId === null) {
    const partialItems = partialMatchQuery.data?.items ?? [];
    return (
      <main className="container">
        <Card>
          <h2>単語「{rawWordKey}」は未登録です</h2>
          <p>登録しますか？</p>
          <Row>
            <button
              onClick={() => {
                if (isPhrase(rawWordKey)) {
                  setShowPhraseConfirm(true);
                  return;
                }
                registerMutation.mutate();
              }}
              disabled={registerMutation.isPending}
            >
              {registerMutation.isPending ? "登録中..." : "単語として登録する"}
            </button>
            <button onClick={() => navigate("/")} disabled={registerMutation.isPending}>
              キャンセル
            </button>
          </Row>
        </Card>
        {partialMatchQuery.isLoading && <Muted as="p">部分一致の単語を検索中...</Muted>}
        {!partialMatchQuery.isLoading && partialItems.length > 0 && (
          <section className="partial-match-section">
            <h3>部分一致した単語</h3>
            <div className="grid">
              {partialItems.map((word) => (
                <WordCard
                  key={word.id}
                  word={word}
                  deleting={deleteFromListMutation.isPending && deletingWordId === word.id}
                  onDelete={(wordId) => deleteFromListMutation.mutate(wordId)}
                />
              ))}
            </div>
          </section>
        )}
        <ConfirmModal
          open={showPhraseConfirm}
          title="熟語の分割登録"
          message={`「${rawWordKey}」は熟語です。単語ごとに登録し、各単語の成句/慣用句にこの熟語を追加します。よろしいですか？`}
          confirmText="登録する"
          onCancel={() => setShowPhraseConfirm(false)}
          onConfirm={() => {
            setShowPhraseConfirm(false);
            registerMutation.mutate();
          }}
        />
      </main>
    );
  }

  if (!word) {
    return (
      <main className="container">
        <p>Loading...</p>
      </main>
    );
  }

  return (
    <main className="container">
      <PageHeader
        title={word.word}
        busy={isBusy}
        actions={
          <>
            <button onClick={() => rescrapeMutation.mutate()} disabled={isBusy}>
              {rescrapeMutation.isPending ? "再取得中..." : "データ再取得"}
            </button>
            <button
              type="button"
              onClick={() => {
                const ok = window.confirm(`単語「${word.word}」を削除しますか？`);
                if (!ok) return;
                deleteWordMutation.mutate();
              }}
              disabled={isBusy}
            >
              {deleteWordMutation.isPending ? "削除中..." : "削除"}
            </button>
            <Link to={`/words/${word.id}/edit`}>編集</Link>
            <Link to="/">一覧へ戻る</Link>
          </>
        }
      />
      <Muted as="p">{word.phonetic || EMPTY_MESSAGES.noPhonetic}</Muted>
      {formEntries.length > 0 && (
        <Muted as="p">
          {formEntries.map(([label, value]) => `${label}: ${value}`).join(" / ")}
        </Muted>
      )}
      <div className="detail-layout">
        <div className="detail-main">
          <WordDefinitions word={word} />
          <DerivationsPanel word={word} />
          <EtymologyMap word={word} />
          <RelatedWords word={word} />
        </div>
        <aside className="detail-side">
          <ImageViewer
            word={word}
            onGenerate={(prompt) => generateImageMutation.mutateAsync(prompt)}
            loading={generateImageMutation.isPending}
          />
          <WordChatPanel wordId={word.id} />
        </aside>
      </div>
    </main>
  );
}
