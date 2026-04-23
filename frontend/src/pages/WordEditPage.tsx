import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Row } from "../components/atom";
import { ConfirmModal } from "../components/ConfirmModal";
import { Tabs } from "../components/common/Tabs";
import {
  WordEditBasicTab,
  WordEditDerivationsTab,
  WordEditEtymologyTab,
  WordEditFormsTab,
  WordEditPhrasesTab,
  WordEditRelatedTab,
  WordEditVariantsTab,
} from "../components/word-edit/WordEditTabs";
import { wordApi } from "../lib/api";
import type {
  ComponentMeaningItem,
  Derivation,
  EtymologyBranch,
  EtymologyComponent,
  EtymologyVariant,
  LanguageChainLink,
  Phrase,
  RelatedWord,
  Word,
} from "../types";

type EditTabKey =
  | "basic"
  | "forms"
  | "phrases"
  | "definitions"
  | "etymology"
  | "etymologyVariants"
  | "derivations"
  | "related";

const EDIT_TABS: Array<{ key: EditTabKey; label: string }> = [
  { key: "basic", label: "基本情報" },
  { key: "forms", label: "活用形" },
  { key: "phrases", label: "成句・慣用句" },
  { key: "etymology", label: "語源" },
  { key: "etymologyVariants", label: "語源バリエーション" },
  { key: "derivations", label: "派生語" },
  { key: "related", label: "関連語" },
];

export function WordEditPage() {
  const params = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const rawWordKey = (params.wordKey ?? "").trim();
  const numericWordId = /^\d+$/.test(rawWordKey) ? Number(rawWordKey) : null;

  const wordQuery = useQuery({
    queryKey: ["word", rawWordKey],
    queryFn: () =>
      numericWordId !== null ? wordApi.get(numericWordId) : wordApi.getByWord(rawWordKey),
    enabled: rawWordKey.length > 0,
  });

  const word = wordQuery.data;
  const [editWord, setEditWord] = useState("");
  const [phonetic, setPhonetic] = useState("");
  const [third, setThird] = useState("");
  const [presentParticiple, setPresentParticiple] = useState("");
  const [pastTense, setPastTense] = useState("");
  const [pastParticiple, setPastParticiple] = useState("");
  const [plural, setPlural] = useState("");
  const [comparative, setComparative] = useState("");
  const [superlative, setSuperlative] = useState("");
  const [uncountable, setUncountable] = useState(false);
  const [phrases, setPhrases] = useState<Array<Pick<Phrase, "text" | "meaning">>>([]);
  const [definitions, setDefinitions] = useState<Word["definitions"]>([]);
  const [derivations, setDerivations] = useState<Derivation[]>([]);
  const [relatedWords, setRelatedWords] = useState<RelatedWord[]>([]);
  const [originWord, setOriginWord] = useState("");
  const [originLanguage, setOriginLanguage] = useState("");
  const [coreImage, setCoreImage] = useState("");
  const [rawDescription, setRawDescription] = useState("");
  const [components, setComponents] = useState<EtymologyComponent[]>([]);
  const [branches, setBranches] = useState<EtymologyBranch[]>([]);
  const [languageChain, setLanguageChain] = useState<LanguageChainLink[]>([]);
  const [componentMeanings, setComponentMeanings] = useState<ComponentMeaningItem[]>([]);
  const [etymologyVariants, setEtymologyVariants] = useState<EtymologyVariant[]>([]);
  const [activeTab, setActiveTab] = useState<EditTabKey>("basic");
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
  const confirmResolverRef = useRef<((result: boolean) => void) | null>(null);

  const openConfirm = (params: {
    title: string;
    message: string;
    confirmVariant?: "default" | "danger";
    confirmText?: string;
    cancelText?: string;
  }) =>
    new Promise<boolean>((resolve) => {
      confirmResolverRef.current = resolve;
      setConfirmState({ open: true, confirmVariant: "default", ...params });
    });

  const closeConfirm = (result: boolean) => {
    confirmResolverRef.current?.(result);
    confirmResolverRef.current = null;
    setConfirmState((prev) => ({ ...prev, open: false }));
  };

  useEffect(() => {
    if (!word) return;
    const forms = word.forms ?? {};
    setEditWord(word.word);
    setPhonetic(word.phonetic ?? "");
    setThird(String(forms.third_person_singular ?? ""));
    setPresentParticiple(String(forms.present_participle ?? ""));
    setPastTense(String(forms.past_tense ?? ""));
    setPastParticiple(String(forms.past_participle ?? ""));
    setPlural(String(forms.plural ?? ""));
    setComparative(String(forms.comparative ?? ""));
    setSuperlative(String(forms.superlative ?? ""));
    setUncountable(Boolean(forms.uncountable));
    setPhrases(
      (word.phrases ?? []).map((item) => ({ text: item.text, meaning: item.meaning ?? "" })),
    );
    setDefinitions(word.definitions);
    setDerivations(word.derivations);
    setRelatedWords(word.related_words);
    setOriginWord(word.etymology?.origin_word ?? "");
    setOriginLanguage(word.etymology?.origin_language ?? "");
    setCoreImage(word.etymology?.core_image ?? "");
    setRawDescription(word.etymology?.raw_description ?? "");
    setComponents(word.etymology?.components ?? []);
    setBranches(word.etymology?.branches ?? []);
    setLanguageChain(word.etymology?.language_chain ?? []);
    setComponentMeanings(word.etymology?.component_meanings ?? []);
    setEtymologyVariants(word.etymology?.etymology_variants ?? []);
  }, [word]);

  const payload = useMemo(() => {
    return {
      word: editWord,
      phonetic: phonetic || null,
      forms: {
        third_person_singular: third || undefined,
        present_participle: presentParticiple || undefined,
        past_tense: pastTense || undefined,
        past_participle: pastParticiple || undefined,
        plural: plural || undefined,
        comparative: comparative || undefined,
        superlative: superlative || undefined,
        uncountable: uncountable || undefined,
      },
      phrases: phrases
        .map((entry) => ({
          text: entry.text.trim(),
          meaning: entry.meaning.trim(),
        }))
        .filter((entry) => Boolean(entry.text)),
      definitions: definitions.map((d, idx) => ({
        id: d.id,
        part_of_speech: d.part_of_speech,
        meaning_en: d.meaning_en,
        meaning_ja: d.meaning_ja,
        example_en: d.example_en,
        example_ja: d.example_ja,
        sort_order: d.sort_order ?? idx,
      })),
      etymology: {
        components,
        origin_word: originWord || null,
        origin_language: originLanguage || null,
        core_image: coreImage || null,
        branches,
        language_chain: languageChain,
        component_meanings: componentMeanings,
        etymology_variants: etymologyVariants,
        raw_description: rawDescription || null,
      },
      derivations: derivations.map((d, idx) => ({
        id: d.id,
        derived_word: d.derived_word,
        part_of_speech: d.part_of_speech,
        meaning_ja: d.meaning_ja,
        sort_order: d.sort_order ?? idx,
      })),
      related_words: relatedWords.map((r) => ({
        id: r.id,
        related_word: r.related_word,
        relation_type: r.relation_type,
        note: r.note,
      })),
    };
  }, [
    editWord,
    phonetic,
    third,
    presentParticiple,
    pastTense,
    pastParticiple,
    plural,
    comparative,
    superlative,
    uncountable,
    phrases,
    definitions,
    components,
    originWord,
    originLanguage,
    coreImage,
    branches,
    languageChain,
    componentMeanings,
    etymologyVariants,
    rawDescription,
    derivations,
    relatedWords,
  ]);
  const initialPayloadSerialized = useMemo(() => {
    if (!word) {
      return "";
    }
    const forms = word.forms ?? {};
    return JSON.stringify({
      word: word.word,
      phonetic: word.phonetic ?? null,
      forms: {
        third_person_singular: String(forms.third_person_singular ?? "") || undefined,
        present_participle: String(forms.present_participle ?? "") || undefined,
        past_tense: String(forms.past_tense ?? "") || undefined,
        past_participle: String(forms.past_participle ?? "") || undefined,
        plural: String(forms.plural ?? "") || undefined,
        comparative: String(forms.comparative ?? "") || undefined,
        superlative: String(forms.superlative ?? "") || undefined,
        uncountable: forms.uncountable ? true : undefined,
      },
      phrases: (word.phrases ?? [])
        .map((entry) => ({
          text: entry.text.trim(),
          meaning: (entry.meaning ?? "").trim(),
        }))
        .filter((entry) => Boolean(entry.text)),
      definitions: (word.definitions ?? []).map((d, idx) => ({
        id: d.id,
        part_of_speech: d.part_of_speech,
        meaning_en: d.meaning_en,
        meaning_ja: d.meaning_ja,
        example_en: d.example_en,
        example_ja: d.example_ja,
        sort_order: d.sort_order ?? idx,
      })),
      etymology: {
        components: word.etymology?.components ?? [],
        origin_word: word.etymology?.origin_word ?? null,
        origin_language: word.etymology?.origin_language ?? null,
        core_image: word.etymology?.core_image ?? null,
        branches: word.etymology?.branches ?? [],
        language_chain: word.etymology?.language_chain ?? [],
        component_meanings: word.etymology?.component_meanings ?? [],
        etymology_variants: word.etymology?.etymology_variants ?? [],
        raw_description: word.etymology?.raw_description ?? null,
      },
      derivations: (word.derivations ?? []).map((d, idx) => ({
        id: d.id,
        derived_word: d.derived_word,
        part_of_speech: d.part_of_speech,
        meaning_ja: d.meaning_ja,
        sort_order: d.sort_order ?? idx,
      })),
      related_words: (word.related_words ?? []).map((r) => ({
        id: r.id,
        related_word: r.related_word,
        relation_type: r.relation_type,
        note: r.note,
      })),
    });
  }, [word]);
  const hasUnsavedChanges = word ? JSON.stringify(payload) !== initialPayloadSerialized : false;

  const saveMutation = useMutation({
    mutationFn: async () => wordApi.updateFull(word!.id, payload),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["word", String(updated.id)] });
      await queryClient.invalidateQueries({ queryKey: ["word", rawWordKey] });
      navigate(`/words/${updated.id}`);
    },
  });
  const deleteWordMutation = useMutation({
    mutationFn: () => wordApi.delete(word!.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["words"] });
      navigate("/");
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
    if (!ok) {
      return;
    }
    onAccept();
  };
  const handleDeleteWord = async () => {
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
      message: `単語「${editWord.trim() || (word?.word ?? "")}」を削除しますか？`,
      confirmText: "削除する",
      cancelText: "キャンセル",
      confirmVariant: "danger",
    });
    if (!ok) {
      return;
    }
    deleteWordMutation.mutate();
  };

  if (!word) {
    return (
      <main className="container">
        <p>Loading...</p>
      </main>
    );
  }

  return (
    <main className="container">
      <Row justify="between">
        <h2>{word.word} の編集</h2>
        <Row>
          <button
            type="button"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || deleteWordMutation.isPending}
          >
            {saveMutation.isPending ? "保存中..." : "保存"}
          </button>
          <button
            type="button"
            className="button-delete"
            onClick={() => void handleDeleteWord()}
            disabled={saveMutation.isPending || deleteWordMutation.isPending}
          >
            {deleteWordMutation.isPending ? "削除中..." : "削除"}
          </button>
          <Link to={`/words/${word.id}`}>キャンセル</Link>
          <Link to={`/words/${word.id}`}>詳細へ戻る</Link>
        </Row>
      </Row>

      <Tabs items={EDIT_TABS} activeKey={activeTab} onChange={setActiveTab} />

      {activeTab === "basic" && (
        <WordEditBasicTab
          editWord={editWord}
          phonetic={phonetic}
          definitions={definitions}
          setEditWord={setEditWord}
          setPhonetic={setPhonetic}
          setDefinitions={setDefinitions}
          confirmRemove={confirmRemove}
        />
      )}

      {activeTab === "forms" && (
        <WordEditFormsTab
          third={third}
          presentParticiple={presentParticiple}
          pastTense={pastTense}
          pastParticiple={pastParticiple}
          plural={plural}
          comparative={comparative}
          superlative={superlative}
          uncountable={uncountable}
          setThird={setThird}
          setPresentParticiple={setPresentParticiple}
          setPastTense={setPastTense}
          setPastParticiple={setPastParticiple}
          setPlural={setPlural}
          setComparative={setComparative}
          setSuperlative={setSuperlative}
          setUncountable={setUncountable}
        />
      )}

      {activeTab === "phrases" && (
        <WordEditPhrasesTab
          phrases={phrases}
          setPhrases={setPhrases}
          confirmRemove={confirmRemove}
        />
      )}

      {activeTab === "etymology" && (
        <WordEditEtymologyTab
          originLanguage={originLanguage}
          originWord={originWord}
          coreImage={coreImage}
          rawDescription={rawDescription}
          components={components}
          branches={branches}
          languageChain={languageChain}
          componentMeanings={componentMeanings}
          setOriginLanguage={setOriginLanguage}
          setOriginWord={setOriginWord}
          setCoreImage={setCoreImage}
          setRawDescription={setRawDescription}
          setComponents={setComponents}
          setBranches={setBranches}
          setLanguageChain={setLanguageChain}
          setComponentMeanings={setComponentMeanings}
          confirmRemove={confirmRemove}
        />
      )}

      {activeTab === "etymologyVariants" && (
        <WordEditVariantsTab
          etymologyVariants={etymologyVariants}
          setEtymologyVariants={setEtymologyVariants}
          confirmRemove={confirmRemove}
        />
      )}

      {activeTab === "derivations" && (
        <WordEditDerivationsTab
          derivations={derivations}
          setDerivations={setDerivations}
          confirmRemove={confirmRemove}
        />
      )}

      {activeTab === "related" && (
        <WordEditRelatedTab
          relatedWords={relatedWords}
          setRelatedWords={setRelatedWords}
          confirmRemove={confirmRemove}
        />
      )}

      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        confirmVariant={confirmState.confirmVariant}
        confirmText={confirmState.confirmText}
        cancelText={confirmState.cancelText}
        disableActions={deleteWordMutation.isPending}
        onCancel={() => closeConfirm(false)}
        onConfirm={() => closeConfirm(true)}
      />
    </main>
  );
}
