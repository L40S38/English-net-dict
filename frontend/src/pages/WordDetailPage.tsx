import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { InflectionBatchModal } from "../components/InflectionBatchModal";
import { Card, Muted, Row } from "../components/atom";
import { wordApi } from "../lib/api";
import { EMPTY_MESSAGES, INFLECTION_LABELS } from "../lib/constants";
import { isNotFoundError } from "../lib/errors";
import type { InflectionAction, InflectionCheckResult } from "../types";

function isPhrase(text: string): boolean {
  return text.trim().split(/\s+/).filter(Boolean).length >= 2;
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
    mutationFn: (options?: {
      inflection_action?: InflectionAction | null;
      lemma_word?: string | null;
    }) => wordApi.create(rawWordKey, options),
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

  const word = wordQuery.data;
  const isBusy =
    wordQuery.isLoading ||
    rescrapeMutation.isPending ||
    generateImageMutation.isPending;
  const forms = word?.forms ?? {};
  const formEntries = [
    {
      key: "third_person_singular",
      label: INFLECTION_LABELS.third_person_singular,
      value: String(forms.third_person_singular ?? ""),
    },
    {
      key: "present_participle",
      label: INFLECTION_LABELS.present_participle,
      value: String(forms.present_participle ?? ""),
    },
    {
      key: "past_tense",
      label: INFLECTION_LABELS.past_tense,
      value: String(forms.past_tense ?? ""),
    },
    {
      key: "past_participle",
      label: INFLECTION_LABELS.past_participle,
      value: String(forms.past_participle ?? ""),
    },
    { key: "plural", label: INFLECTION_LABELS.plural, value: String(forms.plural ?? "") },
    {
      key: "comparative",
      label: INFLECTION_LABELS.comparative,
      value: String(forms.comparative ?? ""),
    },
    {
      key: "superlative",
      label: INFLECTION_LABELS.superlative,
      value: String(forms.superlative ?? ""),
    },
    { key: "uncountable", label: "可算/不可算", value: forms.uncountable ? "不可算" : "" },
  ].filter((item) => item.value);

  const isNotFound = wordQuery.isError && isNotFoundError(wordQuery.error);

  const [deletingWordId, setDeletingWordId] = useState<number | null>(null);
  const [pendingDeleteWord, setPendingDeleteWord] = useState<{ id: number; word: string } | null>(null);
  const [showPhraseConfirm, setShowPhraseConfirm] = useState(false);
  const [showInflectionModal, setShowInflectionModal] = useState(false);
  const [inflectionResult, setInflectionResult] = useState<InflectionCheckResult | null>(null);
  const [isCheckingInflection, setIsCheckingInflection] = useState(false);
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

  const handleRegisterWithCheck = async () => {
    setIsCheckingInflection(true);
    try {
      const response = await wordApi.checkInflection({ word: rawWordKey });
      const result = response.result ?? response.results?.[0] ?? null;
      if (result?.is_inflected) {
        setInflectionResult(result);
        setShowInflectionModal(true);
        return;
      }
      registerMutation.mutate({});
    } finally {
      setIsCheckingInflection(false);
    }
  };

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
                void handleRegisterWithCheck();
              }}
              disabled={isCheckingInflection || registerMutation.isPending}
            >
              {isCheckingInflection || registerMutation.isPending ? "登録中..." : "単語として登録する"}
            </button>
            <button onClick={() => navigate("/")} disabled={isCheckingInflection || registerMutation.isPending}>
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
                  onDelete={(wordId) => setPendingDeleteWord({ id: wordId, word: word.word })}
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
            registerMutation.mutate({});
          }}
        />
        <ConfirmModal
          open={pendingDeleteWord !== null}
          title="削除の確認"
          message={`単語「${pendingDeleteWord?.word ?? ""}」を削除しますか？`}
          confirmText="削除する"
          cancelText="キャンセル"
          confirmVariant="danger"
          disableActions={deleteFromListMutation.isPending}
          onCancel={() => setPendingDeleteWord(null)}
          onConfirm={() => {
            if (!pendingDeleteWord) return;
            deleteFromListMutation.mutate(pendingDeleteWord.id);
            setPendingDeleteWord(null);
          }}
        />
        {showInflectionModal && inflectionResult && (
          <InflectionBatchModal
            open={showInflectionModal}
            title="活用形の確認"
            items={[
              {
                word: inflectionResult.word,
                selectedLemma: inflectionResult.selected_lemma ?? null,
                selectedSpelling: inflectionResult.selected_spelling ?? null,
                lemmaResolution: inflectionResult.lemma_resolution ?? null,
                selectedInflectionType: inflectionResult.selected_inflection_type ?? null,
                lemmaCandidates: (inflectionResult.lemma_candidates ?? []).map((candidate) => ({
                  lemma: candidate.lemma,
                  lemmaWordId: candidate.lemma_word_id ?? null,
                  inflectionType: candidate.inflection_type ?? null,
                })),
                spellingCandidates: (inflectionResult.spelling_candidates ?? []).map((entry) => ({
                  spelling: entry.spelling,
                  source: entry.source ?? null,
                  selectedLemma: entry.selected_lemma ?? null,
                  lemmaResolution: entry.lemma_resolution ?? null,
                  lemmaCandidates: (entry.lemma_candidates ?? []).map((candidate) => ({
                    lemma: candidate.lemma,
                    lemmaWordId: candidate.lemma_word_id ?? null,
                    inflectionType: candidate.inflection_type ?? null,
                  })),
                })),
                suggestion: inflectionResult.suggestion ?? "register_as_is",
              },
            ]}
            onClose={() => setShowInflectionModal(false)}
            onConfirm={(decisions) => {
              const decision = decisions[inflectionResult.word];
              const action = decision?.action ?? "register_as_is";
              const lemmaWord = decision?.lemma ?? inflectionResult.selected_lemma ?? null;
              registerMutation.mutate({
                inflection_action: action,
                lemma_word: action === "register_as_is" ? null : lemmaWord,
              });
              setShowInflectionModal(false);
            }}
          />
        )}
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
            <Link to={`/words/${word.id}/edit`}>編集</Link>
            <Link to="/">一覧へ戻る</Link>
          </>
        }
      />
      <Muted as="p">{word.phonetic || EMPTY_MESSAGES.noPhonetic}</Muted>
      {word.lemma_word_id && (
        <Muted as="p">
          この単語は
          <Link to={`/words/${word.lemma_word_id}`}> {word.lemma_word_text ?? "原形"} </Link>の
          {INFLECTION_LABELS[word.inflection_type ?? "inflection"] ??
            word.inflection_type ??
            "活用形"}
          です。
        </Muted>
      )}
      {formEntries.length > 0 && (
        <Muted as="p">
          {formEntries.map((entry, idx) => {
            const linked = word.inflected_forms?.find(
              (item) => item.word.toLowerCase() === entry.value.toLowerCase(),
            );
            return (
              <span key={entry.key}>
                {idx > 0 ? " / " : ""}
                {entry.label}:{" "}
                {linked ? <Link to={`/words/${linked.word_id}`}>{entry.value}</Link> : entry.value}
              </span>
            );
          })}
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
            title="イメージ画像"
            entityLabel={word.word}
            images={word.images}
            fetchDefaultPrompt={() => wordApi.getDefaultImagePrompt(word.id)}
            onGenerate={(prompt) => generateImageMutation.mutateAsync(prompt)}
            loading={generateImageMutation.isPending}
          />
          <WordChatPanel wordId={word.id} />
        </aside>
      </div>
    </main>
  );
}
