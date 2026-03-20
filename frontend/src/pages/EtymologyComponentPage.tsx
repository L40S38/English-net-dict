import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ComponentChatPanel } from "../components/ComponentChatPanel";
import { ConfirmModal } from "../components/ConfirmModal";
import { PageHeader } from "../components/PageHeader";
import { WordLinkRow } from "../components/WordLinkRow";
import { WordCard } from "../components/WordCard";
import { Card, Muted, Stack } from "../components/atom";
import { componentApi, wordApi } from "../lib/api";
import { EMPTY_MESSAGES } from "../lib/constants";

export function EtymologyComponentPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const componentText = decodeURIComponent(params.componentText ?? "").trim();
  const [deletingWordId, setDeletingWordId] = useState<number | null>(null);
  const [showRegisterConfirm, setShowRegisterConfirm] = useState(true);
  const componentMeaning = (searchParams.get("meaning") ?? "").trim();
  const fromWord = (searchParams.get("from") ?? "").trim();
  const componentQuery = useQuery({
    queryKey: ["etymology-component", componentText],
    queryFn: () => componentApi.get(componentText),
    enabled: componentText.length > 0,
    retry: false,
  });

  const wordsQuery = useQuery({
    queryKey: ["words", "etymology-component", componentText],
    queryFn: () => wordApi.searchByEtymologyComponent(componentText),
    enabled: componentText.length > 0,
  });
  const rescrapeMutation = useMutation({
    mutationFn: () => componentApi.rescrape(componentText),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["words", "etymology-component", componentText],
      });
    },
  });
  const createComponentMutation = useMutation({
    mutationFn: () => componentApi.create(componentText),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["etymology-component", componentText],
      });
      await queryClient.invalidateQueries({
        queryKey: ["words", "etymology-component", componentText],
      });
    },
  });
  const deleteWordMutation = useMutation({
    mutationFn: (wordId: number) => wordApi.delete(wordId),
    onMutate: (wordId) => {
      setDeletingWordId(wordId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
      await queryClient.invalidateQueries({
        queryKey: ["words", "etymology-component", componentText],
      });
    },
    onSettled: () => {
      setDeletingWordId(null);
    },
  });
  const genericMeanings = new Set(["語根要素", "接頭要素", "語源要素"]);
  const isNotRegistered =
    componentQuery.isError &&
    axios.isAxiosError(componentQuery.error) &&
    componentQuery.error.response?.status === 404;
  const fromApi = (wordsQuery.data?.resolved_meaning ?? "").trim();
  let resolvedMeaning = fromApi;
  if (!resolvedMeaning) {
    const fromQuery = componentMeaning.trim();
    if (fromQuery && !genericMeanings.has(fromQuery)) {
      resolvedMeaning = fromQuery;
    } else {
      for (const word of wordsQuery.data?.items ?? []) {
        for (const component of word.etymology?.components ?? []) {
          const text = String(component.text ?? "")
            .trim()
            .toLowerCase();
          const meaning = String(component.meaning ?? "").trim();
          if (text === componentText.toLowerCase() && meaning && !genericMeanings.has(meaning)) {
            resolvedMeaning = meaning;
            break;
          }
        }
        if (resolvedMeaning) {
          break;
        }
      }
      if (!resolvedMeaning) {
        resolvedMeaning = genericMeanings.has(fromQuery) ? "" : fromQuery;
      }
    }
  }
  const wiktionaryInfo = componentQuery.data;
  const isBusy =
    wordsQuery.isLoading ||
    componentQuery.isLoading ||
    rescrapeMutation.isPending ||
    createComponentMutation.isPending;

  if (isNotRegistered) {
    return (
      <main className="container">
        <Card>
          <h2>語源要素「{componentText}」は未登録です</h2>
          <p>登録しますか？</p>
          <div className="row">
            <button
              type="button"
              onClick={() => setShowRegisterConfirm(true)}
              disabled={createComponentMutation.isPending}
            >
              {createComponentMutation.isPending ? "登録中..." : "語源要素として登録する"}
            </button>
            <Link to={fromWord ? `/words/${encodeURIComponent(fromWord)}` : "/"}>キャンセル</Link>
          </div>
        </Card>
        <ConfirmModal
          open={isNotRegistered && showRegisterConfirm}
          title="語源要素の登録"
          message={`語源要素「${componentText}」を登録しますか？`}
          confirmText="登録する"
          onCancel={() => setShowRegisterConfirm(false)}
          onConfirm={() => {
            setShowRegisterConfirm(false);
            createComponentMutation.mutate();
          }}
        />
      </main>
    );
  }

  return (
    <main className="container">
      <PageHeader
        title={`語源要素: ${componentText || "-"}`}
        busy={isBusy}
        actions={
          <>
            <button
              type="button"
              onClick={() => rescrapeMutation.mutate()}
              disabled={!componentText || rescrapeMutation.isPending}
            >
              {rescrapeMutation.isPending ? "再取得中..." : "データ再取得"}
            </button>
            {fromWord && <Link to={`/words/${encodeURIComponent(fromWord)}`}>元の単語へ戻る</Link>}
            <Link to="/">一覧へ戻る</Link>
          </>
        }
      />
      <div className="detail-layout">
        <div className="detail-main">
          <Card>
            <h3>Wiktionary由来</h3>
            <Stack>
              <Card variant="sub" stack>
                <strong>意味</strong>
                {(wiktionaryInfo?.wiktionary_meanings ?? []).length === 0 && (
                  <Muted>{EMPTY_MESSAGES.noData}</Muted>
                )}
                {(wiktionaryInfo?.wiktionary_meanings ?? []).map((meaning, idx) => (
                  <Muted key={`${meaning}-${idx}`} as="p">
                    {meaning}
                  </Muted>
                ))}
              </Card>
              <Card variant="sub" stack>
                <strong>関連語</strong>
                {(wiktionaryInfo?.wiktionary_related_terms ?? []).length === 0 && (
                  <Muted>{EMPTY_MESSAGES.noData}</Muted>
                )}
                {(wiktionaryInfo?.wiktionary_related_terms ?? []).map((term) => (
                  <Card key={term} variant="sub" stack>
                    <WordLinkRow value={term} secondary="Wiktionary" />
                  </Card>
                ))}
              </Card>
              <Card variant="sub" stack>
                <strong>派生語</strong>
                {(wiktionaryInfo?.wiktionary_derived_terms ?? []).length === 0 && (
                  <Muted>{EMPTY_MESSAGES.noData}</Muted>
                )}
                {(wiktionaryInfo?.wiktionary_derived_terms ?? []).map((term) => (
                  <Card key={term} variant="sub" stack>
                    <WordLinkRow value={term} secondary="Wiktionary" />
                  </Card>
                ))}
              </Card>
              {wiktionaryInfo?.wiktionary_source_url && (
                <Muted as="p">
                  出典:{" "}
                  <a href={wiktionaryInfo.wiktionary_source_url} target="_blank" rel="noreferrer">
                    {wiktionaryInfo.wiktionary_source_url}
                  </a>
                </Muted>
              )}
            </Stack>
          </Card>
          {wordsQuery.isLoading && <Muted as="p">単語データを読み込み中...</Muted>}
          {!wordsQuery.isLoading && (wordsQuery.data?.items.length ?? 0) === 0 && (
            <Muted as="p">{EMPTY_MESSAGES.noResults}</Muted>
          )}
          <Card>
            <h3>語源要素を含む単語</h3>
            <section className="grid">
              {(wordsQuery.data?.items ?? []).map((word) => (
                <WordCard
                  key={word.id}
                  word={word}
                  deleting={deleteWordMutation.isPending && deletingWordId === word.id}
                  onDelete={(wordId) => deleteWordMutation.mutate(wordId)}
                />
              ))}
            </section>
          </Card>
        </div>
        <aside className="detail-side">
          <Card stack>{resolvedMeaning && <Muted as="p">意味: {resolvedMeaning}</Muted>}</Card>
          {componentText && <ComponentChatPanel componentText={componentText} />}
        </aside>
      </div>
    </main>
  );
}
