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
import { Tabs } from "../components/common/Tabs";
import {
  GroupEditAiTab,
  GroupEditBasicTab,
  GroupEditBulkTab,
  GroupEditItemsTab,
  GroupEditManualTab,
} from "../components/group-edit";
import type { GroupCandidateSelectionPayload } from "../components/group-edit/types";
import type { WordGroupItem } from "../types";
import { Muted } from "../components/atom";
import { createPhrasesBulk } from "../lib/createPhrasesBulk";
import { createWordsWithInflectionCheck } from "../lib/createWordsWithInflectionCheck";
import { groupApi, phraseApi, wordApi } from "../lib/api";
import { groupNameLengthErrorMessage, groupNameTooLong } from "../lib/groupNameLimits";

type GroupEditTabKey = "basic" | "manual" | "bulk" | "ai" | "items";

const GROUP_EDIT_TABS: Array<{ key: GroupEditTabKey; label: string }> = [
  { key: "basic", label: "基本情報" },
  { key: "manual", label: "手動追加" },
  { key: "bulk", label: "一括追加" },
  { key: "ai", label: "AIで追加" },
  { key: "items", label: "登録済み" },
];

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

  const [activeTab, setActiveTab] = useState<GroupEditTabKey>("basic");
  const [groupDraft, setGroupDraft] = useState<{ name: string; description: string } | null>(null);
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
  const [bulkFlowProgress, setBulkFlowProgress] = useState<{ completed: number; total: number } | null>(null);
  const [pendingRemoveItem, setPendingRemoveItem] = useState<WordGroupItem | null>(null);
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
    mutationFn: (payload: Parameters<typeof groupApi.addItem>[1]) => groupApi.addItem(groupId, payload),
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
        onChunkProgress: (completed, totalCount) => setBulkFlowProgress({ completed, total: totalCount }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
  });

  const bulkCreatePhrasesMutation = useMutation({
    mutationFn: (phrases: string[]) =>
      createPhrasesBulk(phrases, {
        onChunkProgress: (completed, totalCount) => setBulkFlowProgress({ completed, total: totalCount }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
    },
  });

  const group = groupQuery.data;
  const currentNameDraft = groupDraft?.name ?? group?.name ?? "";
  const currentDescriptionDraft = groupDraft?.description ?? group?.description ?? "";

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
        targetPhraseIds = Array.from(new Set([...targetPhraseIds, ...rechecked.found.map((item) => item.id)]));
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

  const addSelectedCandidates = async (payload: GroupCandidateSelectionPayload) => {
    if (payload.word_ids.length > 0 || payload.phrase_ids.length > 0) {
      await bulkAddMutation.mutateAsync({
        word_ids: payload.word_ids,
        phrase_ids: payload.phrase_ids,
      });
    }
    for (const example of payload.examples) {
      await addItemMutation.mutateAsync({
        item_type: "example",
        word_id: example.word_id,
        definition_id: example.definition_id,
      });
    }
  };
  const formatGroupItemLabel = (item: WordGroupItem): string => {
    if (item.item_type === "word") {
      return `単語「${item.word ?? "-"}」`;
    }
    if (item.item_type === "phrase") {
      return `熟語「${item.phrase_text ?? "-"}」`;
    }
    return `例文「${item.example_en ?? "-"}」`;
  };

  const groupEditTabs = GROUP_EDIT_TABS.map((item) => {
    if (item.key !== "items") {
      return item;
    }
    return { ...item, label: `登録済み (${group?.items.length ?? 0})` };
  });

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
          <Tabs items={groupEditTabs} activeKey={activeTab} onChange={setActiveTab} />

          {activeTab === "basic" && (
            <GroupEditBasicTab
              currentNameDraft={currentNameDraft}
              currentDescriptionDraft={currentDescriptionDraft}
              onChangeName={(value) =>
                setGroupDraft({
                  name: value,
                  description: currentDescriptionDraft,
                })
              }
              onChangeDescription={(value) =>
                setGroupDraft({
                  name: currentNameDraft,
                  description: value,
                })
              }
              onSave={() => {
                if (groupNameTooLong(currentNameDraft)) {
                  setGroupNameErrorOpen(true);
                  return;
                }
                updateGroupMutation.mutate();
              }}
              isSaving={updateGroupMutation.isPending}
              saveDisabled={updateGroupMutation.isPending || !currentNameDraft.trim()}
              nameLengthHint={groupNameLengthErrorMessage()}
            />
          )}

          {activeTab === "manual" && (
            <GroupEditManualTab
              groupItems={group.items}
              onAddSelection={addSelectedCandidates}
              disableActions={isBusy}
            />
          )}

          {activeTab === "bulk" && (
            <GroupEditBulkTab
              bulkText={bulkText}
              onChangeBulkText={(value) => {
                setBulkText(value);
                setBulkFlowError(null);
              }}
              bulkFlowError={bulkFlowError}
              isBulkWordFlowPending={isBulkWordFlowPending}
              bulkFlowProgress={bulkFlowProgress}
              bulkProgressPercent={bulkProgressPercent}
              onCheckAndOpenConfirm={() => {
                void (async () => {
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
                })();
              }}
              bulkMissing={bulkMissing}
            />
          )}

          {activeTab === "ai" && (
            <GroupEditAiTab
              groupId={groupId}
              groupItems={group.items}
              onAddSelection={addSelectedCandidates}
              disableActions={isBusy}
            />
          )}

          {activeTab === "items" && (
            <GroupEditItemsTab
              group={group}
              isRemoving={removeItemMutation.isPending}
              onRemove={(item) => setPendingRemoveItem(item)}
            />
          )}
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
      <ConfirmModal
        open={pendingRemoveItem !== null}
        title="削除の確認"
        message={`${pendingRemoveItem ? formatGroupItemLabel(pendingRemoveItem) : "項目"}を削除しますか？`}
        confirmText="削除する"
        cancelText="キャンセル"
        confirmVariant="danger"
        disableActions={removeItemMutation.isPending}
        onConfirm={() => {
          if (!pendingRemoveItem) return;
          removeItemMutation.mutate(pendingRemoveItem.id);
          setPendingRemoveItem(null);
        }}
        onCancel={() => setPendingRemoveItem(null)}
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
