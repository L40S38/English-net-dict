import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { BulkImport } from "../components/BulkImport";
import { ConfirmModal } from "../components/ConfirmModal";
import {
  InflectionBatchModal,
  type InflectionBatchItem,
  type InflectionBatchDecision,
} from "../components/InflectionBatchModal";
import { WordCard } from "../components/WordCard";
import { WordForm } from "../components/WordForm";
import { LoadingBanner, Muted } from "../components/atom";
import { createWordsWithInflectionCheck } from "../lib/createWordsWithInflectionCheck";
import { wordApi } from "../lib/api";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { InflectionAction, SortOrder, Word, WordSortBy } from "../types";

const SORT_BY_OPTIONS: Array<{ value: WordSortBy; label: string }> = [
  { value: "last_viewed_at", label: "最終閲覧日時" },
  { value: "created_at", label: "追加日時" },
  { value: "updated_at", label: "最終更新日" },
  { value: "word", label: "アルファベット順" },
];

const SORT_ORDER_OPTIONS: Array<{ value: SortOrder; label: string }> = [
  { value: "desc", label: "降順" },
  { value: "asc", label: "昇順" },
];

function isPhrase(text: string): boolean {
  return text.trim().split(/\s+/).filter(Boolean).length >= 2;
}

function compareWords(a: Word, b: Word, sortBy: WordSortBy, sortOrder: SortOrder): number {
  const sign = sortOrder === "asc" ? 1 : -1;
  const compareWord = a.word.localeCompare(b.word, undefined, { sensitivity: "base" });

  if (sortBy === "word") {
    if (compareWord !== 0) {
      return compareWord * sign;
    }
    return (a.id - b.id) * sign;
  }

  if (sortBy === "last_viewed_at") {
    const aValue = a.last_viewed_at;
    const bValue = b.last_viewed_at;
    if (!aValue && !bValue) {
      return (a.id - b.id) * sign;
    }
    if (!aValue) {
      return 1;
    }
    if (!bValue) {
      return -1;
    }
    const aDate = new Date(aValue).getTime();
    const bDate = new Date(bValue).getTime();
    if (aDate !== bDate) {
      return (aDate - bDate) * sign;
    }
    return (a.id - b.id) * sign;
  }

  const getDate = (word: Word) => {
    if (sortBy === "created_at") {
      return new Date(word.created_at).getTime();
    }
    return new Date(word.updated_at).getTime();
  };
  const aDate = getDate(a);
  const bDate = getDate(b);
  if (aDate !== bDate) {
    return (aDate - bDate) * sign;
  }
  return (a.id - b.id) * sign;
}

export function HomePage() {
  const [deletingWordId, setDeletingWordId] = useState<number | null>(null);
  const [sessionWords, setSessionWords] = useState<Word[]>([]);
  const [bulkProgress, setBulkProgress] = useState<{ completed: number; total: number } | null>(
    null,
  );
  const [confirmState, setConfirmState] = useState<{
    open: boolean;
    title: string;
    message: string;
    confirmVariant?: "default" | "danger";
    confirmText?: string;
    cancelText?: string;
  }>({
    open: false,
    title: "",
    message: "",
    confirmVariant: "default",
  });
  const [sortBy, setSortBy] = useState<WordSortBy>("last_viewed_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [isCheckingInflectionForm, setIsCheckingInflectionForm] = useState(false);
  const [inflectionModalState, setInflectionModalState] = useState<{
    open: boolean;
    title: string;
    items: Array<{
      word: string;
      selectedLemma?: string | null;
      selectedInflectionType?: string | null;
      lemmaCandidates?: Array<{
        lemma: string;
        lemmaWordId?: number | null;
        inflectionType?: string | null;
      }>;
      suggestion: InflectionAction;
    }>;
  }>({
    open: false,
    title: "",
    items: [],
  });
  const queryClient = useQueryClient();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const confirmResolverRef = useRef<((result: boolean) => void) | null>(null);
  const inflectionResolverRef = useRef<
    ((result: Record<string, InflectionBatchDecision> | null) => void) | null
  >(null);

  const openConfirm = (params: {
    title: string;
    message: string;
    confirmVariant?: "default" | "danger";
    confirmText?: string;
    cancelText?: string;
  }) =>
    new Promise<boolean>((resolve) => {
      confirmResolverRef.current = resolve;
      setConfirmState({ open: true, ...params });
    });

  const closeConfirm = (result: boolean) => {
    confirmResolverRef.current?.(result);
    confirmResolverRef.current = null;
    setConfirmState((prev) => ({ ...prev, open: false }));
  };

  const openInflectionModal = (params: {
    title: string;
    items: InflectionBatchItem[];
  }) =>
    new Promise<Record<string, InflectionBatchDecision> | null>((resolve) => {
      inflectionResolverRef.current = resolve;
      setInflectionModalState({
        open: true,
        title: params.title,
        items: params.items,
      });
    });

  const closeInflectionModal = (result: Record<string, InflectionBatchDecision> | null) => {
    inflectionResolverRef.current?.(result);
    inflectionResolverRef.current = null;
    setInflectionModalState({ open: false, title: "", items: [] });
  };

  const wordsQuery = useInfiniteQuery({
    queryKey: ["words", sortBy, sortOrder],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      wordApi.list({
        page: Number(pageParam),
        page_size: 10,
        sort_by: sortBy,
        sort_order: sortOrder,
      }),
    getNextPageParam: (lastPage, allPages) => {
      const loadedCount = allPages.reduce((acc, page) => acc + page.items.length, 0);
      return loadedCount < lastPage.total ? allPages.length + 1 : undefined;
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: {
      word: string;
      options?: { inflection_action?: InflectionAction | null; lemma_word?: string | null };
    }) => wordApi.create(payload.word, payload.options),
    onSuccess: async (createdWords) => {
      setSessionWords((prev) => {
        const seenIds = new Set(prev.map((item) => item.id));
        const next = [...prev];
        for (let i = createdWords.length - 1; i >= 0; i -= 1) {
          const created = createdWords[i];
          if (seenIds.has(created.id)) {
            continue;
          }
          seenIds.add(created.id);
          next.unshift(created);
        }
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
  });

  const bulkMutation = useMutation({
    mutationFn: async (words: string[]) => {
      setBulkProgress({ completed: 0, total: words.length });
      return createWordsWithInflectionCheck(words, openInflectionModal, {
        onChunkProgress: (completed, totalCount) => setBulkProgress({ completed, total: totalCount }),
      });
    },
    onSuccess: async (createdWords) => {
      setSessionWords((prev) => {
        const seenIds = new Set(prev.map((item) => item.id));
        const next = [...prev];
        for (let i = createdWords.length - 1; i >= 0; i -= 1) {
          const created = createdWords[i];
          if (seenIds.has(created.id)) {
            continue;
          }
          seenIds.add(created.id);
          next.unshift(created);
        }
        return next;
      });
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
    onSettled: () => {
      setBulkProgress(null);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (wordId: number) => wordApi.delete(wordId),
    onMutate: (wordId) => {
      setDeletingWordId(wordId);
    },
    onSuccess: async (_, wordId) => {
      setSessionWords((prev) => prev.filter((word) => word.id !== wordId));
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
    onSettled: () => {
      setDeletingWordId(null);
    },
  });

  const backendWords = useMemo(
    () => wordsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [wordsQuery.data?.pages],
  );
  const displayWords = useMemo(() => {
    const sessionWordIds = new Set(sessionWords.map((word) => word.id));
    const dedupedBackendWords = backendWords.filter((word) => !sessionWordIds.has(word.id));
    const merged = [...sessionWords, ...dedupedBackendWords];
    return merged.sort((a, b) => compareWords(a, b, sortBy, sortOrder));
  }, [backendWords, sessionWords, sortBy, sortOrder]);

  useEffect(() => {
    const target = loadMoreRef.current;
    if (!target) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) {
          return;
        }
        if (!wordsQuery.hasNextPage || wordsQuery.isFetchingNextPage) {
          return;
        }
        void wordsQuery.fetchNextPage();
      },
      { rootMargin: "200px" },
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [wordsQuery.fetchNextPage, wordsQuery.hasNextPage, wordsQuery.isFetchingNextPage]);

  const isBusy =
    wordsQuery.isLoading ||
    createMutation.isPending ||
    bulkMutation.isPending ||
    deleteMutation.isPending;

  return (
    <main className="container">
      <div className="page-header">
        <h1>単語一覧</h1>
        {isBusy && <LoadingBanner>サーバーと通信中...</LoadingBanner>}
      </div>
      <WordForm
        onSubmit={async (word) => {
          if (isPhrase(word)) {
            const ok = await openConfirm({
              title: "熟語の分割登録",
              message: `「${word}」は熟語です。単語ごとに登録し、各単語の成句/慣用句にこの熟語を追加します。よろしいですか？`,
              confirmText: "登録する",
            });
            if (!ok) {
              return false;
            }
          }
          setIsCheckingInflectionForm(true);
          const inflection = await wordApi.checkInflection({ word }).finally(() => {
            setIsCheckingInflectionForm(false);
          });
          const result = inflection.result ?? inflection.results?.[0];
          if (result?.is_inflected) {
            const selectedActions = await openInflectionModal({
              title: "活用形チェック",
              items: [
                {
                  word: result.word,
                  selectedLemma: result.selected_lemma ?? null,
                  selectedSpelling: result.selected_spelling ?? null,
                  lemmaResolution: result.lemma_resolution ?? null,
                  selectedInflectionType: result.selected_inflection_type ?? null,
                  lemmaCandidates: (result.lemma_candidates ?? []).map((candidate) => ({
                    lemma: candidate.lemma,
                    lemmaWordId: candidate.lemma_word_id ?? null,
                    inflectionType: candidate.inflection_type ?? null,
                  })),
                  spellingCandidates: (result.spelling_candidates ?? []).map((entry) => ({
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
                  suggestion: result.suggestion ?? "register_as_is",
                },
              ],
            });
            if (!selectedActions) {
              return false;
            }
            const decision = selectedActions[result.word];
            const action = decision?.action ?? result.suggestion ?? "register_as_is";
            const lemmaWord = decision?.lemma ?? result.selected_lemma ?? null;
            await createMutation.mutateAsync({
              word,
              options: {
                inflection_action: action,
                lemma_word: action === "register_as_is" ? null : lemmaWord,
              },
            });
            return true;
          }
          await createMutation.mutateAsync({ word });
          return true;
        }}
        disabled={isBusy || isCheckingInflectionForm}
        loading={createMutation.isPending || isCheckingInflectionForm}
      />
      <BulkImport
        onImport={async (words) => {
          const phrases = words.filter((word) => isPhrase(word));
          if (phrases.length > 0) {
            const preview = phrases.slice(0, 5).join("\n- ");
            const suffix = phrases.length > 5 ? `\n- ...他 ${phrases.length - 5} 件` : "";
            const ok = await openConfirm({
              title: "一括登録の確認",
              message: `以下の熟語は単語ごとに登録され、各単語の成句/慣用句にも追加されます。\n\n- ${preview}${suffix}\n\n続行しますか？`,
              confirmText: "続行する",
            });
            if (!ok) {
              return false;
            }
          }
          await bulkMutation.mutateAsync(words);
          return true;
        }}
        disabled={isBusy}
        loading={bulkMutation.isPending}
        progress={bulkProgress}
      />
      <hr className="section-divider" />
      {wordsQuery.isLoading && <Muted as="p">単語データを読み込み中...</Muted>}
      <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ minWidth: 200 }}>
          <small>並び替え項目</small>
          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as WordSortBy)}
            disabled={wordsQuery.isFetching}
          >
            {SORT_BY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ minWidth: 140 }}>
          <small>順序</small>
          <select
            value={sortOrder}
            onChange={(event) => setSortOrder(event.target.value as SortOrder)}
            disabled={wordsQuery.isFetching}
          >
            {SORT_ORDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <section className="grid">
        {displayWords.map((word) => (
          <WordCard
            key={word.id}
            word={word}
            deleting={deleteMutation.isPending && deletingWordId === word.id}
            onDelete={(wordId) => {
              const target = displayWords.find((item) => item.id === wordId);
              void openConfirm({
                title: "削除の確認",
                message: `単語「${target?.word ?? wordId}」を削除しますか？`,
                confirmText: "削除する",
                cancelText: "キャンセル",
                confirmVariant: "danger",
              }).then((ok) => {
                if (ok) {
                  deleteMutation.mutate(wordId);
                }
              });
            }}
          />
        ))}
        {!wordsQuery.isLoading && displayWords.length === 0 && (
          <Muted as="p">{EMPTY_MESSAGES.noResults}</Muted>
        )}
      </section>
      {!wordsQuery.isLoading && <div ref={loadMoreRef} style={{ height: 1 }} />}
      {wordsQuery.isFetchingNextPage && <Muted as="p">さらに読み込み中...</Muted>}
      {!wordsQuery.isLoading && !wordsQuery.hasNextPage && displayWords.length > 0 && (
        <Muted as="p">すべて表示しました。</Muted>
      )}
      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        confirmVariant={confirmState.confirmVariant}
        confirmText={confirmState.confirmText}
        cancelText={confirmState.cancelText}
        onCancel={() => closeConfirm(false)}
        onConfirm={() => closeConfirm(true)}
      />
      <InflectionBatchModal
        open={inflectionModalState.open}
        title={inflectionModalState.title}
        items={inflectionModalState.items}
        onClose={() => closeInflectionModal(null)}
        onConfirm={(actions) => closeInflectionModal(actions)}
      />
    </main>
  );
}
