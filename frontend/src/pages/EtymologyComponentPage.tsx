import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ComponentChatPanel } from "../components/ComponentChatPanel";
import { PageHeader } from "../components/PageHeader";
import { WordLinkRow } from "../components/WordLinkRow";
import { WordCard } from "../components/WordCard";
import { Card, Muted, Stack } from "../components/atom";
import { componentApi, wordApi } from "../lib/api";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { ComponentDisplayMode, Word } from "../types";

export function EtymologyComponentPage() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const componentText = decodeURIComponent(params.componentText ?? "").trim();
  const [deletingWordId, setDeletingWordId] = useState<number | null>(null);
  const [updatingModeWordId, setUpdatingModeWordId] = useState<number | null>(null);
  const [displayModeDrafts, setDisplayModeDrafts] = useState<
    Partial<Record<number, ComponentDisplayMode>>
  >({});
  const componentMeaning = (searchParams.get("meaning") ?? "").trim();
  const fromWord = (searchParams.get("from") ?? "").trim();

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
  const updateDisplayModeMutation = useMutation({
    mutationFn: async ({
      wordId,
      mode,
    }: {
      wordId: number;
      mode: ComponentDisplayMode;
    }) => {
      const targetWord = (wordsQuery.data?.items ?? []).find((word) => word.id === wordId);
      if (!targetWord?.etymology) return;
      const normalizedComponentText = componentText.toLowerCase();
      const components = (targetWord.etymology.components ?? []).map((component) => {
        const isTarget =
          String(component.text ?? "")
            .trim()
            .toLowerCase() === normalizedComponentText;
        return isTarget ? { ...component, display_mode: mode } : component;
      });
      return wordApi.updateEtymology(wordId, {
        ...targetWord.etymology,
        components,
        branches: targetWord.etymology.branches ?? [],
      });
    },
    onMutate: ({ wordId }) => {
      setUpdatingModeWordId(wordId);
    },
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ["words", "etymology-component", componentText],
      });
      await queryClient.invalidateQueries({ queryKey: ["word", String(variables.wordId)] });
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
    onSettled: () => {
      setUpdatingModeWordId(null);
    },
  });
  const genericMeanings = new Set(["語根要素", "接頭要素", "語源要素"]);
  const resolvedMeaning = useMemo(() => {
    const fromApi = (wordsQuery.data?.resolved_meaning ?? "").trim();
    if (fromApi) {
      return fromApi;
    }
    const fromQuery = componentMeaning.trim();
    if (fromQuery && !genericMeanings.has(fromQuery)) {
      return fromQuery;
    }
    for (const word of wordsQuery.data?.items ?? []) {
      for (const component of word.etymology?.components ?? []) {
        const text = String(component.text ?? "")
          .trim()
          .toLowerCase();
        const meaning = String(component.meaning ?? "").trim();
        if (text === componentText.toLowerCase() && meaning && !genericMeanings.has(meaning)) {
          return meaning;
        }
      }
    }
    // Keep meaning blank when only generic fallback exists.
    return genericMeanings.has(fromQuery) ? "" : fromQuery;
  }, [componentMeaning, componentText, wordsQuery.data?.items]);
  const wiktionaryInfo = wordsQuery.data?.wiktionary;
  const currentDisplayMode = (word: Word): ComponentDisplayMode => {
    const component = (word.etymology?.components ?? []).find(
      (item) =>
        String(item.text ?? "")
          .trim()
          .toLowerCase() === componentText.toLowerCase(),
    );
    return component?.display_mode ?? "auto";
  };

  return (
    <main className="container">
      <PageHeader
        title={`語源要素: ${componentText || "-"}`}
        busy={wordsQuery.isLoading || rescrapeMutation.isPending}
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
                {(wiktionaryInfo?.meanings ?? []).length === 0 && (
                  <Muted>{EMPTY_MESSAGES.noData}</Muted>
                )}
                {(wiktionaryInfo?.meanings ?? []).map((meaning, idx) => (
                  <Muted key={`${meaning}-${idx}`} as="p">
                    {meaning}
                  </Muted>
                ))}
              </Card>
              <Card variant="sub" stack>
                <strong>関連語</strong>
                {(wiktionaryInfo?.related_terms ?? []).length === 0 && (
                  <Muted>{EMPTY_MESSAGES.noData}</Muted>
                )}
                {(wiktionaryInfo?.related_terms ?? []).map((term) => (
                  <Card key={term} variant="sub" stack>
                    <WordLinkRow value={term} secondary="Wiktionary" />
                  </Card>
                ))}
              </Card>
              <Card variant="sub" stack>
                <strong>派生語</strong>
                {(wiktionaryInfo?.derived_terms ?? []).length === 0 && (
                  <Muted>{EMPTY_MESSAGES.noData}</Muted>
                )}
                {(wiktionaryInfo?.derived_terms ?? []).map((term) => (
                  <Card key={term} variant="sub" stack>
                    <WordLinkRow value={term} secondary="Wiktionary" />
                  </Card>
                ))}
              </Card>
              {wiktionaryInfo?.source_url && (
                <Muted as="p">
                  出典:{" "}
                  <a href={wiktionaryInfo.source_url} target="_blank" rel="noreferrer">
                    {wiktionaryInfo.source_url}
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
          <Card stack>
            <h3>語源要素の表示モード（編集）</h3>
            <Muted as="p">この語源要素を含む各単語ごとに、表示モードを編集できます。</Muted>
            {(wordsQuery.data?.items ?? []).length === 0 && (
              <Muted as="p">編集対象の単語がありません。</Muted>
            )}
            {(wordsQuery.data?.items ?? []).map((word) => {
              const current = currentDisplayMode(word);
              const value = displayModeDrafts[word.id] ?? current;
              const pending =
                updateDisplayModeMutation.isPending && updatingModeWordId === word.id;
              return (
                <Card key={word.id} variant="sub" stack>
                  <Link to={`/words/${word.id}`}>{word.word}</Link>
                  <Stack gap="sm">
                    <select
                      value={value}
                      onChange={(e) =>
                        setDisplayModeDrafts((prev) => ({
                          ...prev,
                          [word.id]: e.target.value as ComponentDisplayMode,
                        }))
                      }
                      disabled={pending}
                    >
                      <option value="auto">auto（推奨）</option>
                      <option value="word">word（単語として表示）</option>
                      <option value="morpheme">morpheme（語源要素として表示）</option>
                      <option value="both">both（単語と語源要素を両方表示）</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => updateDisplayModeMutation.mutate({ wordId: word.id, mode: value })}
                      disabled={pending || value === current}
                    >
                      {pending ? "保存中..." : "保存"}
                    </button>
                  </Stack>
                </Card>
              );
            })}
          </Card>
          <Card stack>{resolvedMeaning && <Muted as="p">意味: {resolvedMeaning}</Muted>}</Card>
          {componentText && <ComponentChatPanel componentText={componentText} />}
        </aside>
      </div>
    </main>
  );
}
