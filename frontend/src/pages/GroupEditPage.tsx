import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { ConfirmModal } from "../components/ConfirmModal";
import { Card, Muted, Row, Stack } from "../components/atom";
import { groupApi, wordApi } from "../lib/api";
import { groupNameLengthErrorMessage, groupNameTooLong } from "../lib/groupNameLimits";
import type { GroupSuggestCandidate } from "../types";

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
  const [bulkMissingWords, setBulkMissingWords] = useState<string[]>([]);
  const [bulkFoundWordIds, setBulkFoundWordIds] = useState<number[]>([]);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);

  const groupQuery = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => groupApi.get(groupId),
    enabled: Number.isFinite(groupId) && groupId > 0,
  });

  const wordSearchQuery = useQuery({
    queryKey: ["group", "word-search", wordKeyword],
    queryFn: () => wordApi.list({ q: wordKeyword.trim(), page_size: 20 }),
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
    mutationFn: (wordIds: number[]) => groupApi.bulkAddItems(groupId, wordIds),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const bulkCreateWordsMutation = useMutation({
    mutationFn: (words: string[]) => wordApi.bulkCreate(words),
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
    bulkCreateWordsMutation.isPending;

  const parseBulkWords = (raw: string) => {
    const unique = new Set<string>();
    for (const line of raw.split(/\r?\n/)) {
      const value = line.trim();
      if (!value || unique.has(value)) continue;
      unique.add(value);
    }
    return Array.from(unique);
  };

  const runBulkAddFlow = async (missingWords: string[], foundWordIds: number[]) => {
    let targetWordIds = [...foundWordIds];
    if (missingWords.length > 0) {
      const created = await bulkCreateWordsMutation.mutateAsync(missingWords);
      targetWordIds = Array.from(new Set([...targetWordIds, ...created.map((item) => item.id)]));
    }
    if (targetWordIds.length > 0) {
      await bulkAddMutation.mutateAsync(targetWordIds);
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    }
    setBulkText("");
    setBulkMissingWords([]);
    setBulkFoundWordIds([]);
    setBulkConfirmOpen(false);
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
                onChange={(event) => setBulkText(event.target.value)}
                placeholder="例: apple&#10;take off&#10;ASAP"
              />
            </label>
            <button
              type="button"
              disabled={bulkAddMutation.isPending || bulkCreateWordsMutation.isPending}
              onClick={async () => {
                const words = parseBulkWords(bulkText);
                if (words.length === 0) return;
                const checked = await wordApi.check(words);
                const foundIds = checked.found.map((item) => item.id);
                if (checked.not_found.length === 0) {
                  await runBulkAddFlow([], foundIds);
                  return;
                }
                setBulkMissingWords(checked.not_found);
                setBulkFoundWordIds(foundIds);
                setBulkConfirmOpen(true);
              }}
            >
              {bulkAddMutation.isPending || bulkCreateWordsMutation.isPending
                ? "一括追加中..."
                : "確認して追加"}
            </button>
            {bulkMissingWords.length > 0 && (
              <Muted as="p">未登録: {bulkMissingWords.join(", ")}</Muted>
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
        title="未登録単語をDBに追加しますか？"
        message={
          bulkMissingWords.length > 0
            ? `次の単語/熟語は未登録です。\n${bulkMissingWords.join(", ")}\n\nDB登録してからグループへ追加しますか？`
            : "未登録単語はありません。"
        }
        confirmText="登録して追加"
        cancelText="登録済みのみ追加"
        onConfirm={() => void runBulkAddFlow(bulkMissingWords, bulkFoundWordIds)}
        onCancel={() => {
          void runBulkAddFlow([], bulkFoundWordIds);
        }}
      />
    </main>
  );
}
