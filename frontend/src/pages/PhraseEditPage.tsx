import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ConfirmModal } from "../components/ConfirmModal";
import { Tabs } from "../components/common/Tabs";
import { Row } from "../components/atom";
import { phraseApi } from "../lib/api";
import { PhraseEditBasicTab } from "../components/phrase-edit/PhraseEditBasicTab";
import { PhraseEditDefinitionsTab } from "../components/phrase-edit/PhraseEditDefinitionsTab";
import {
  PhraseEditRelationsTab,
  type PhraseRelatedItem,
} from "../components/phrase-edit/PhraseEditRelationsTab";
import { PhraseEditWordsTab } from "../components/phrase-edit/PhraseEditWordsTab";
import type { Phrase, PhraseDefinition, WordSummary } from "../types";

type EditTabKey = "basic" | "definitions" | "words" | "related";

const EDIT_TABS: Array<{ key: EditTabKey; label: string }> = [
  { key: "basic", label: "基本情報" },
  { key: "definitions", label: "定義" },
  { key: "words", label: "構成語" },
  { key: "related", label: "関連語" },
];

function createRelatedItemsFromPhrase(data: Phrase): PhraseRelatedItem[] {
  const items: PhraseRelatedItem[] = [];
  let nextId = -1;
  for (const text of data.wiktionary_synonyms ?? []) {
    items.push({ id: nextId--, related_word: text, relation_type: "synonym", note: "" });
  }
  for (const text of data.wiktionary_antonyms ?? []) {
    items.push({ id: nextId--, related_word: text, relation_type: "antonym", note: "" });
  }
  for (const text of data.wiktionary_see_also ?? []) {
    items.push({ id: nextId--, related_word: text, relation_type: "confusable", note: "" });
  }
  for (const text of data.wiktionary_derived_terms ?? []) {
    items.push({ id: nextId--, related_word: text, relation_type: "cognate", note: "" });
  }
  for (const text of data.wiktionary_phrases ?? []) {
    items.push({ id: nextId--, related_word: text, relation_type: "phrase", note: "" });
  }
  return items;
}

export function PhraseEditPage() {
  const params = useParams();
  const phraseId = Number(params.phraseId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const phraseQuery = useQuery({
    queryKey: ["phrase", phraseId],
    queryFn: () => phraseApi.get(phraseId),
    enabled: Number.isFinite(phraseId) && phraseId > 0,
  });

  const [text, setText] = useState("");
  const [meaning, setMeaning] = useState("");
  const [definitions, setDefinitions] = useState<PhraseDefinition[]>([]);
  const [words, setWords] = useState<WordSummary[]>([]);
  const [relatedItems, setRelatedItems] = useState<PhraseRelatedItem[]>([]);
  const [activeTab, setActiveTab] = useState<EditTabKey>("basic");
  const [confirmState, setConfirmState] = useState<{
    open: boolean;
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    confirmVariant?: "default" | "danger";
  }>({
    open: false,
    title: "",
    message: "",
    confirmVariant: "default",
  });
  const confirmResolverRef = useRef<((result: boolean) => void) | null>(null);

  useEffect(() => {
    if (!phraseQuery.data) return;
    setText(phraseQuery.data.text);
    setMeaning(phraseQuery.data.meaning ?? "");
    setDefinitions(phraseQuery.data.definitions ?? []);
    setWords(phraseQuery.data.words ?? []);
    setRelatedItems(createRelatedItemsFromPhrase(phraseQuery.data));
  }, [phraseQuery.data]);

  const payload = useMemo(
    () => ({
      text: text.trim(),
      meaning: meaning.trim(),
      definitions: definitions.map((item, idx) => ({
        id: item.id > 0 ? item.id : null,
        part_of_speech: item.part_of_speech,
        meaning_en: item.meaning_en,
        meaning_ja: item.meaning_ja,
        example_en: item.example_en,
        example_ja: item.example_ja,
        sort_order: idx,
      })),
      word_ids: words.map((word) => word.id),
      wiktionary_synonyms: relatedItems
        .filter((item) => item.relation_type === "synonym")
        .map((item) => item.related_word.trim())
        .filter(Boolean),
      wiktionary_antonyms: relatedItems
        .filter((item) => item.relation_type === "antonym")
        .map((item) => item.related_word.trim())
        .filter(Boolean),
      wiktionary_see_also: relatedItems
        .filter((item) => item.relation_type === "confusable")
        .map((item) => item.related_word.trim())
        .filter(Boolean),
      wiktionary_derived_terms: relatedItems
        .filter((item) => item.relation_type === "cognate")
        .map((item) => item.related_word.trim())
        .filter(Boolean),
      wiktionary_phrases: relatedItems
        .filter((item) => item.relation_type === "phrase")
        .map((item) => item.related_word.trim())
        .filter(Boolean),
    }),
    [text, meaning, definitions, words, relatedItems],
  );
  const initialPayload = useMemo(() => {
    if (!phraseQuery.data) {
      return null;
    }
    return {
      text: phraseQuery.data.text.trim(),
      meaning: (phraseQuery.data.meaning ?? "").trim(),
      definitions: (phraseQuery.data.definitions ?? []).map((item, idx) => ({
        id: item.id > 0 ? item.id : null,
        part_of_speech: item.part_of_speech,
        meaning_en: item.meaning_en,
        meaning_ja: item.meaning_ja,
        example_en: item.example_en,
        example_ja: item.example_ja,
        sort_order: idx,
      })),
      word_ids: (phraseQuery.data.words ?? []).map((word) => word.id),
      wiktionary_synonyms: (phraseQuery.data.wiktionary_synonyms ?? []).map((item) => item.trim()).filter(Boolean),
      wiktionary_antonyms: (phraseQuery.data.wiktionary_antonyms ?? []).map((item) => item.trim()).filter(Boolean),
      wiktionary_see_also: (phraseQuery.data.wiktionary_see_also ?? []).map((item) => item.trim()).filter(Boolean),
      wiktionary_derived_terms: (phraseQuery.data.wiktionary_derived_terms ?? []).map((item) => item.trim()).filter(Boolean),
      wiktionary_phrases: (phraseQuery.data.wiktionary_phrases ?? []).map((item) => item.trim()).filter(Boolean),
    };
  }, [phraseQuery.data]);
  const hasUnsavedChanges =
    initialPayload != null && JSON.stringify(payload) !== JSON.stringify(initialPayload);

  const openConfirm = (params: {
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    confirmVariant?: "default" | "danger";
  }) =>
    new Promise<boolean>((resolve) => {
      confirmResolverRef.current = resolve;
      setConfirmState({
        open: true,
        title: params.title,
        message: params.message,
        confirmText: params.confirmText,
        cancelText: params.cancelText,
        confirmVariant: params.confirmVariant ?? "default",
      });
    });

  const closeConfirm = (result: boolean) => {
    confirmResolverRef.current?.(result);
    confirmResolverRef.current = null;
    setConfirmState((prev) => ({ ...prev, open: false }));
  };

  const saveMutation = useMutation({
    mutationFn: () => phraseApi.updateFull(phraseId, payload),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["phrase", phraseId] });
      await queryClient.invalidateQueries({ queryKey: ["phrases"] });
      navigate(`/phrases/${updated.id}`);
    },
  });

  const enrichMutation = useMutation({
    mutationFn: () => phraseApi.enrich(phraseId),
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

  const confirmRemove = async (targetLabel: string, onAccept: () => void) => {
    const ok = await openConfirm({
      title: "削除の確認",
      message: `${targetLabel}を本当に削除しますか？`,
      confirmText: "削除する",
      cancelText: "キャンセル",
      confirmVariant: "danger",
    });
    if (ok) {
      onAccept();
    }
  };

  const handleDeletePhrase = async () => {
    if (hasUnsavedChanges) {
      const proceed = await openConfirm({
        title: "未保存の変更があります",
        message: "保存せずに削除しますか？",
        confirmText: "続行",
        cancelText: "キャンセル",
      });
      if (!proceed) {
        return;
      }
    }
    const ok = await openConfirm({
      title: "削除の確認",
      message: `熟語「${text.trim() || (phraseQuery.data?.text ?? "")}」を削除しますか？`,
      confirmText: "削除する",
      cancelText: "キャンセル",
      confirmVariant: "danger",
    });
    if (!ok) {
      return;
    }
    deletePhraseMutation.mutate();
  };

  if (!phraseQuery.data) {
    return (
      <main className="container">
        <p>Loading...</p>
      </main>
    );
  }

  return (
    <main className="container">
      <Row justify="between">
        <h2>{phraseQuery.data.text} の編集</h2>
        <Row>
          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || deletePhraseMutation.isPending}
          >
            {saveMutation.isPending ? "保存中..." : "保存"}
          </button>
          <button
            type="button"
            className="button-delete"
            onClick={() => void handleDeletePhrase()}
            disabled={saveMutation.isPending || deletePhraseMutation.isPending}
          >
            {deletePhraseMutation.isPending ? "削除中..." : "削除"}
          </button>
          <Link to={`/phrases/${phraseQuery.data.id}`}>キャンセル</Link>
          <Link to={`/phrases/${phraseQuery.data.id}`}>詳細へ戻る</Link>
        </Row>
      </Row>

      <Tabs items={EDIT_TABS} activeKey={activeTab} onChange={setActiveTab} />

      {activeTab === "basic" && (
        <PhraseEditBasicTab
          text={text}
          meaning={meaning}
          setText={setText}
          setMeaning={setMeaning}
          onEnrich={() => enrichMutation.mutate()}
          enriching={enrichMutation.isPending}
        />
      )}
      {activeTab === "definitions" && (
        <PhraseEditDefinitionsTab
          definitions={definitions}
          setDefinitions={setDefinitions}
          confirmRemove={confirmRemove}
        />
      )}
      {activeTab === "words" && (
        <PhraseEditWordsTab words={words} setWords={setWords} confirmRemove={confirmRemove} />
      )}
      {activeTab === "related" && (
        <PhraseEditRelationsTab
          relatedItems={relatedItems}
          setRelatedItems={setRelatedItems}
          confirmRemove={confirmRemove}
        />
      )}

      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        confirmText={confirmState.confirmText}
        cancelText={confirmState.cancelText}
        confirmVariant={confirmState.confirmVariant}
        disableActions={deletePhraseMutation.isPending}
        onCancel={() => closeConfirm(false)}
        onConfirm={() => closeConfirm(true)}
      />
    </main>
  );
}
