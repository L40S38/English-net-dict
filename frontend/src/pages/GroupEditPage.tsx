import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ConfirmModal } from "../components/ConfirmModal";
import {
  InflectionBatchModal,
  type InflectionBatchDecision,
  type InflectionBatchItem,
} from "../components/InflectionBatchModal";
import { PageHeader } from "../components/PageHeader";
import { Card, Muted, Row, Stack } from "../components/atom";
import { createPhrasesBulk } from "../lib/createPhrasesBulk";
import { createWordsWithInflectionCheck } from "../lib/createWordsWithInflectionCheck";
import { groupApi, phraseApi, wordApi } from "../lib/api";
import { groupNameLengthErrorMessage, groupNameTooLong } from "../lib/groupNameLimits";
import type { GroupSuggestCandidate } from "../types";

function formatBulkFlowApiError(error: unknown): string {
  if (error instanceof AxiosError) {
    const data = error.response?.data;
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
      if (Array.isArray(detail)) {
        return detail.map((entry) => JSON.stringify(entry)).join("; ");
      }
    }
    if (error.message) {
      return error.message;
    }
  }
  return "一括追加に失敗しました。しばらくしてから再度お試しください。";
}

export function GroupEditPage() {
  const params = useParams();
  const groupId = Number(params.groupId);
  const queryClient = useQueryClient();

  const [groupDraft, setGroupDraft] = useState<{ name: string; description: string } | null>(null);
  const [wordKeyword, setWordKeyword] = useState("");
  const [aiKeywords, setAiKeywords] = useState("");
  const [selectedCandidates, setSelectedCandidates] = useState<Set<string>>(new Set());
  const [groupNameErrorOpen, setGroupNameErrorOpen] = useState(false);
  const [bulkText, setBulkText] = useState("");
  const [bulkMissing, setBulkMissing] = useState<{ words: string[]; phrases: string[] }>({
    words: [],
    phrases: [],
  });
  const [bulkFound, setBulkFound] = useState<{ wordIds: number[]; phraseIds: number[] }>({
    wordIds: [],
    phraseIds: [],
  });
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [bulkFlowError, setBulkFlowError] = useState<string | null>(null);
  const [bulkFlowProgress, setBulkFlowProgress] = useState<{ completed: number; total: number } | null>(
    null,
  );
  const bulkFlowInFlightRef = useRef(false);
  const [inflectionModalState, setInflectionModalState] = useState<{
    open: boolean;
    title: string;
    items: InflectionBatchItem[];
  }>({
    open: false,
    title: "",
    items: [],
  });
  const inflectionResolverRef = useRef<
    ((result: Record<string, InflectionBatchDecision> | null) => void) | null
  >(null);

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => groupApi.get(groupId),
    enabled: Number.isFinite(groupId) && groupId > 0,
  });

  const wordSearchQuery = useQuery({
    queryKey: ["group", "word-search", wordKeyword],
    queryFn: () => wordApi.searchForGroup({ q: wordKeyword.trim(), page_size: 20 }),
    enabled: wordKeyword.trim().length > 0,
  });

  const suggestMutation = useMutation({
    mutationFn: (keywords: string[]) => groupApi.suggest(groupId, { keywords, limit: 50 }),
  });

  const updateGroupMutation = useMutation({
    mutationFn: () =>
      groupApi.update(groupId, { name: currentNameDraft, description: currentDescriptionDraft }),
    onSuccess: async () => {
      setGroupDraft(null);
      await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const addItemMutation = useMutation({
    mutationFn: (payload: Parameters<typeof groupApi.addItem>[1]) =>
      groupApi.addItem(groupId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const removeItemMutation = useMutation({
    mutationFn: (itemId: number) => groupApi.removeItem(groupId, itemId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const bulkAddMutation = useMutation({
    mutationFn: (payload: { word_ids?: number[]; phrase_ids?: number[] }) =>
      groupApi.bulkAddItems(groupId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const openInflectionModal = (params: { title: string; items: InflectionBatchItem[] }) =>
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

  const bulkCreateWithInflectionMutation = useMutation({
    mutationFn: (words: string[]) =>
      createWordsWithInflectionCheck(words, openInflectionModal, {
        onChunkProgress: (completed, totalCount) =>
          setBulkFlowProgress({ completed, total: totalCount }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
  });
  const bulkCreatePhrasesMutation = useMutation({
    mutationFn: (phrases: string[]) =>
      createPhrasesBulk(phrases, {
        onChunkProgress: (completed, totalCount) =>
          setBulkFlowProgress({ completed, total: totalCount }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
  });

  const group = groupQuery.data;
  const currentNameDraft = groupDraft?.name ?? group?.name ?? "";
  const currentDescriptionDraft = groupDraft?.description ?? group?.description ?? "";
  const candidates = suggestMutation.data?.candidates ?? [];
  const candidateKey = (candidate: GroupSuggestCandidate) =>
    `${candidate.item_type}:${candidate.word_id ?? ""}:${candidate.definition_id ?? ""}:${candidate.phrase_id ?? ""}:${candidate.phrase_text ?? ""}`;

  if (!groupId || Number.isNaN(groupId)) {
    return (
      <main className="container">
        <Muted as="p">グループIDが不正です。</Muted>
      </main>
    );
  }

  const isBusy =
    groupQuery.isLoading ||
    updateGroupMutation.isPending ||
    addItemMutation.isPending ||
    removeItemMutation.isPending ||
    suggestMutation.isPending ||
    bulkAddMutation.isPending ||
    bulkCreateWithInflectionMutation.isPending ||
    bulkCreatePhrasesMutation.isPending;

  const parseBulkEntries = (raw: string) => {
    const unique = new Set<string>();
    const words: string[] = [];
    const phrases: string[] = [];
    for (const line of raw.split(/\r?\n/)) {
      const value = line.trim();
      if (!value || unique.has(value)) continue;
      unique.add(value);
      if (/\s/.test(value)) {
        phrases.push(value);
      } else {
        words.push(value);
      }
    }
    return { words, phrases };
  };

  const isBulkWordFlowPending =
    bulkAddMutation.isPending ||
    bulkCreateWithInflectionMutation.isPending ||
    bulkCreatePhrasesMutation.isPending;
  const bulkProgressPercent =
    bulkFlowProgress && bulkFlowProgress.total > 0
      ? Math.round((bulkFlowProgress.completed / bulkFlowProgress.total) * 100)
      : 0;

  const runBulkAddFlow = async (
    missingEntries: { words: string[]; phrases: string[] },
    foundEntries: { wordIds: number[]; phraseIds: number[] },
  ) => {
    if (bulkFlowInFlightRef.current) {
      return;
    }
    bulkFlowInFlightRef.current = true;
    setBulkFlowError(null);
    try {
      let targetWordIds = [...foundEntries.wordIds];
      let targetPhraseIds = [...foundEntries.phraseIds];
      if (missingEntries.words.length > 0) {
        const created = await bulkCreateWithInflectionMutation.mutateAsync(missingEntries.words);
        targetWordIds = Array.from(new Set([...targetWordIds, ...created.map((item) => item.id)]));
      }
      if (missingEntries.phrases.length > 0) {
        await bulkCreatePhrasesMutation.mutateAsync(missingEntries.phrases);
        const rechecked = await phraseApi.check(missingEntries.phrases);
        if (rechecked.not_found.length > 0) {
          throw new Error(`次の熟語を登録できませんでした: ${rechecked.not_found.join(", ")}`);
        }
        targetPhraseIds = Array.from(
          new Set([...targetPhraseIds, ...rechecked.found.map((item) => item.id)]),
        );
      }
      if (targetWordIds.length > 0 || targetPhraseIds.length > 0) {
        if (missingEntries.words.length === 0 && missingEntries.phrases.length === 0) {
          setBulkFlowProgress({ completed: 0, total: 1 });
        }
        await bulkAddMutation.mutateAsync({
          word_ids: targetWordIds,
          phrase_ids: targetPhraseIds,
        });
        await queryClient.invalidateQueries({ queryKey: ["words"] });
      }
      setBulkText("");
      setBulkMissing({ words: [], phrases: [] });
      setBulkFound({ wordIds: [], phraseIds: [] });
    } catch (error) {
      setBulkFlowError(formatBulkFlowApiError(error));
      setBulkMissing({ words: [], phrases: [] });
      setBulkFound({ wordIds: [], phraseIds: [] });
    } finally {
      setBulkFlowProgress(null);
      bulkFlowInFlightRef.current = false;
    }
  };

  return (
    <main className="container">
      <PageHeader
        title={group ? `編集: ${group.name}` : "グループ編集"}
        busy={isBusy}
        actions={
          <>
            <Link to={`/groups/${groupId}`}>詳細へ戻る</Link>
            <Link to="/groups">一覧へ戻る</Link>
          </>
        }
      />

      {!groupQuery.isLoading && !group && <Muted as="p">グループが見つかりません。</Muted>}

      {group && (
        <>
          <Card stack>
            <h3>グループ名/説明</h3>
            <label>
              <small>名前</small>
              <input
                value={currentNameDraft}
                onChange={(event) =>
                  setGroupDraft({
                    name: event.target.value,
                    description: currentDescriptionDraft,
                  })
                }
              />
            </label>
            <Muted as="p">{groupNameLengthErrorMessage()}</Muted>
            <label>
              <small>説明</small>
              <textarea
                rows={3}
                value={currentDescriptionDraft}
                onChange={(event) =>
                  setGroupDraft({
                    name: currentNameDraft,
                    description: event.target.value,
                  })
                }
              />
            </label>
            <Row>
              <button
                type="button"
                onClick={() => {
                  if (groupNameTooLong(currentNameDraft)) {
                    setGroupNameErrorOpen(true);
                    return;
                  }
                  updateGroupMutation.mutate();
                }}
                disabled={updateGroupMutation.isPending || !currentNameDraft.trim()}
              >
                {updateGroupMutation.isPending ? "保存中..." : "保存"}
              </button>
            </Row>
          </Card>

          <Card stack>
            <h3>手動追加</h3>
            <label>
              <small>単語/熟語を検索</small>
              <input
                value={wordKeyword}
                onChange={(event) => setWordKeyword(event.target.value)}
                placeholder="登録済み単語を検索"
              />
            </label>
            {(wordSearchQuery.data?.items ?? []).map((word) => (
              <Card key={word.id} variant="sub" stack>
                <Row>
                  <Link to={`/words/${word.id}`}>{word.word}</Link>
                  <button
                    type="button"
                    onClick={() => addItemMutation.mutate({ item_type: "word", word_id: word.id })}
                    disabled={addItemMutation.isPending}
                  >
                    単語追加
                  </button>
                </Row>
                {(word.definitions ?? []).slice(0, 2).map((definition) => (
                  <Row key={definition.id}>
                    <span
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        alignItems: "baseline",
                        gap: "0.5rem",
                      }}
                    >
                      <strong>{word.word}</strong>
                      <Muted as="span">
                        [{definition.part_of_speech}] {definition.meaning_ja}
                      </Muted>
                      {definition.meaning_en ? (
                        <Muted as="span" style={{ fontSize: "0.9em" }}>
                          — {definition.meaning_en}
                        </Muted>
                      ) : null}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        addItemMutation.mutate({
                          item_type: "example",
                          word_id: word.id,
                          definition_id: definition.id,
                        })
                      }
                      disabled={addItemMutation.isPending}
                    >
                      例文追加
                    </button>
                  </Row>
                ))}

                {(word.phrases ?? [])
                  .filter((entry) => {
                    const q = wordKeyword.trim().toLowerCase();
                    if (!q) return true;
                    const text = `${entry.text} ${entry.meaning ?? ""}`.toLowerCase();
                    return text.includes(q);
                  })
                  .slice(0, 5)
                  .map((entry) => (
                    <Row key={entry.id}>
                      <span
                        style={{
                          display: "flex",
                          flexWrap: "wrap",
                          alignItems: "baseline",
                          gap: "0.5rem",
                        }}
                      >
                        <strong>{entry.text}</strong>
                        {entry.meaning ? <Muted as="span">— {entry.meaning}</Muted> : null}
                        <Muted as="span" style={{ fontSize: "0.9em" }}>
                          （熟語）
                        </Muted>
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          addItemMutation.mutate({
                            item_type: "phrase",
                            phrase_id: entry.id,
                            phrase_text: entry.text,
                            phrase_meaning: entry.meaning,
                          })
                        }
                        disabled={addItemMutation.isPending}
                      >
                        熟語追加
                      </button>
                    </Row>
                  ))}
              </Card>
            ))}
          </Card>

          <Card stack>
            <h3>単語一括追加</h3>
            <label>
              <small>1行1単語/熟語</small>
              <textarea
                rows={5}
                value={bulkText}
                onChange={(event) => {
                  setBulkText(event.target.value);
                  setBulkFlowError(null);
                }}
                placeholder="例: apple&#10;take off&#10;ASAP"
              />
            </label>
            {bulkFlowError && (
              <p role="alert" style={{ color: "#b91c1c", margin: "0.25rem 0 0" }}>
                {bulkFlowError}
              </p>
            )}
            {isBulkWordFlowPending && bulkFlowProgress && (
              <div className="bulk-progress" aria-live="polite">
                <div className="bulk-progress-label">
                  進捗: {bulkFlowProgress.completed} / {bulkFlowProgress.total} ({bulkProgressPercent}%)
                </div>
                <div
                  className="bulk-progress-track"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={bulkProgressPercent}
                >
                  <div className="bulk-progress-fill" style={{ width: `${bulkProgressPercent}%` }} />
                </div>
              </div>
            )}
            <button
              type="button"
              disabled={isBulkWordFlowPending}
              onClick={async () => {
                const entries = parseBulkEntries(bulkText);
                if (entries.words.length === 0 && entries.phrases.length === 0) return;
                setBulkFlowError(null);
                const [checkedWords, checkedPhrases] = await Promise.all([
                  wordApi.check(entries.words),
                  phraseApi.check(entries.phrases),
                ]);
                const foundEntries = {
                  wordIds: checkedWords.found.map((item) => item.id),
                  phraseIds: checkedPhrases.found.map((item) => item.id),
                };
                const missingEntries = {
                  words: checkedWords.not_found,
                  phrases: checkedPhrases.not_found,
                };
                if (missingEntries.words.length === 0 && missingEntries.phrases.length === 0) {
                  await runBulkAddFlow({ words: [], phrases: [] }, foundEntries);
                  return;
                }
                setBulkMissing(missingEntries);
                setBulkFound(foundEntries);
                setBulkConfirmOpen(true);
              }}
            >
              {isBulkWordFlowPending
                ? `一括追加中... (${bulkFlowProgress?.completed ?? 0}/${bulkFlowProgress?.total ?? 0})`
                : "確認して追加"}
            </button>
            {(bulkMissing.words.length > 0 || bulkMissing.phrases.length > 0) && (
              <Muted as="p">
                未登録:
                {bulkMissing.words.length > 0 ? ` 単語(${bulkMissing.words.join(", ")})` : ""}
                {bulkMissing.phrases.length > 0 ? ` 熟語(${bulkMissing.phrases.join(", ")})` : ""}
              </Muted>
            )}
          </Card>

          <Card stack>
            <h3>AIで追加</h3>
            <label>
              <small>キーワード（カンマ区切り）</small>
              <input
                value={aiKeywords}
                onChange={(event) => setAiKeywords(event.target.value)}
                placeholder="例: food, cook, restaurant"
              />
            </label>
            <button
              type="button"
              onClick={() =>
                suggestMutation.mutate(
                  aiKeywords
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                )
              }
              disabled={suggestMutation.isPending}
            >
              {suggestMutation.isPending ? "検索中..." : "AIで検索"}
            </button>
            {candidates.map((candidate) => {
              const key = candidateKey(candidate);
              const checked = selectedCandidates.has(key);
              return (
                <Card key={key} variant="sub" stack>
                  <label
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.5rem",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) =>
                        setSelectedCandidates((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(key);
                          else next.delete(key);
                          return next;
                        })
                      }
                    />
                    <span style={{ flex: 1 }}>
                      {candidate.item_type === "word" && (
                        <>
                          <strong>{candidate.word}</strong>
                          <Muted as="span"> (score: {candidate.score.toFixed(1)})</Muted>
                        </>
                      )}
                      {candidate.item_type === "phrase" && (
                        <>
                          <strong>{candidate.phrase_text}</strong>
                          {candidate.phrase_meaning ? (
                            <Muted as="span"> — {candidate.phrase_meaning}</Muted>
                          ) : null}
                          <Muted as="span"> (score: {candidate.score.toFixed(1)})</Muted>
                        </>
                      )}
                      {candidate.item_type === "example" && (
                        <>
                          <strong>{candidate.word}</strong>
                          {(candidate.definition_part_of_speech ||
                            candidate.definition_meaning_ja) && (
                            <Muted as="span">
                              {" "}
                              {candidate.definition_part_of_speech
                                ? `[${candidate.definition_part_of_speech}]`
                                : ""}
                              {candidate.definition_meaning_ja
                                ? ` ${candidate.definition_meaning_ja}`
                                : ""}
                            </Muted>
                          )}
                          <span> — {candidate.example_en || candidate.example_ja || "—"}</span>
                          <Muted as="span"> (score: {candidate.score.toFixed(1)})</Muted>
                        </>
                      )}
                    </span>
                  </label>
                </Card>
              );
            })}
            {candidates.length > 0 && (
              <button
                type="button"
                onClick={async () => {
                  for (const candidate of candidates) {
                    const key = candidateKey(candidate);
                    if (!selectedCandidates.has(key)) continue;
                    await addItemMutation.mutateAsync({
                      item_type: candidate.item_type,
                      word_id: candidate.word_id,
                      definition_id: candidate.definition_id,
                      phrase_id: candidate.phrase_id,
                      phrase_text: candidate.phrase_text,
                      phrase_meaning: candidate.phrase_meaning,
                    });
                  }
                  setSelectedCandidates(new Set());
                }}
                disabled={addItemMutation.isPending || selectedCandidates.size === 0}
              >
                選択候補を追加
              </button>
            )}
          </Card>

          <Card stack>
            <h3>登録済みアイテム（削除）</h3>
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
                    {item.word && (
                      <p>
                        <strong>{item.word}</strong>
                        {item.definition_part_of_speech && (
                          <Muted as="span"> [{item.definition_part_of_speech}]</Muted>
                        )}
                        {item.definition_meaning_ja && (
                          <Muted as="span"> {item.definition_meaning_ja}</Muted>
                        )}
                      </p>
                    )}
                    <Muted as="p">{item.example_en}</Muted>
                    {item.example_ja && <Muted as="p">{item.example_ja}</Muted>}
                  </Stack>
                )}
                <Row>
                  <button
                    type="button"
                    className="modal-cancel"
                    onClick={() => removeItemMutation.mutate(item.id)}
                    disabled={removeItemMutation.isPending}
                  >
                    削除
                  </button>
                </Row>
              </Card>
            ))}
          </Card>
        </>
      )}

      <ConfirmModal
        open={groupNameErrorOpen}
        title="グループ名が長すぎます"
        message={groupNameLengthErrorMessage()}
        variant="alert"
        confirmText="閉じる"
        onConfirm={() => setGroupNameErrorOpen(false)}
        onCancel={() => setGroupNameErrorOpen(false)}
      />
      <ConfirmModal
        open={bulkConfirmOpen}
        title="未登録単語/熟語をDBに追加しますか？"
        message={
          bulkMissing.words.length > 0 || bulkMissing.phrases.length > 0
            ? [
                "次の項目は未登録です。",
                bulkMissing.words.length > 0 ? `単語: ${bulkMissing.words.join(", ")}` : "",
                bulkMissing.phrases.length > 0 ? `熟語: ${bulkMissing.phrases.join(", ")}` : "",
                "",
                "DB登録してからグループへ追加しますか？",
              ]
                .filter(Boolean)
                .join("\n")
            : "未登録項目はありません。"
        }
        confirmText="登録して追加"
        cancelText="登録済みのみ追加"
        disableActions={isBulkWordFlowPending}
        onConfirm={() => {
          setBulkConfirmOpen(false);
          void runBulkAddFlow(bulkMissing, bulkFound);
        }}
        onCancel={() => {
          setBulkConfirmOpen(false);
          void runBulkAddFlow({ words: [], phrases: [] }, bulkFound);
        }}
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
