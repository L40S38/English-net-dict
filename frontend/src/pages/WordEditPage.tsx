import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Card, Field, Row } from "../components/atom";
import { BranchFormBlock } from "../components/BranchFormBlock";
import { ComponentFormBlock } from "../components/ComponentFormBlock";
import { ComponentMeaningFormBlock } from "../components/ComponentMeaningFormBlock";
import { ConfirmModal } from "../components/ConfirmModal";
import { DefinitionFormBlock } from "../components/DefinitionFormBlock";
import { DerivationFormBlock } from "../components/DerivationFormBlock";
import { EtymologyVariantFormBlock } from "../components/EtymologyVariantFormBlock";
import { LanguageChainFormBlock } from "../components/LanguageChainFormBlock";
import { PhraseFormBlock } from "../components/PhraseFormBlock";
import { RelatedWordFormBlock } from "../components/RelatedWordFormBlock";
import { Tabs } from "../components/common/Tabs";
import { wordApi } from "../lib/api";
import { POS_OPTIONS } from "../lib/constants";
import type {
  Derivation,
  EtymologyBranch,
  EtymologyComponent,
  EtymologyVariant,
  LanguageChainLink,
  PhraseEntry,
  RelatedWord,
  Word,
} from "../types";

type ComponentMeaningEntry = { text: string; meaning: string };

function normalizePhraseEntries(rawPhrases: unknown): PhraseEntry[] {
  if (!Array.isArray(rawPhrases)) {
    return [];
  }
  return rawPhrases.flatMap((item) => {
    if (typeof item === "string") {
      const phrase = item.trim();
      return phrase ? [{ phrase, meaning: "" }] : [];
    }
    if (!item || typeof item !== "object") {
      return [];
    }
    const phrase = String((item as { phrase?: string; text?: string }).phrase ?? (item as { text?: string }).text ?? "").trim();
    if (!phrase) {
      return [];
    }
    const meaning = String(
      (item as { meaning?: string; meaning_en?: string; meaning_ja?: string }).meaning ??
        (item as { meaning_en?: string }).meaning_en ??
        (item as { meaning_ja?: string }).meaning_ja ??
        "",
    ).trim();
    return [{ phrase, meaning }];
  });
}

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
  const [phrases, setPhrases] = useState<PhraseEntry[]>([]);
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
  const [componentMeanings, setComponentMeanings] = useState<ComponentMeaningEntry[]>([]);
  const [etymologyVariants, setEtymologyVariants] = useState<EtymologyVariant[]>([]);
  const [activeTab, setActiveTab] = useState<EditTabKey>("basic");
  const [confirmState, setConfirmState] = useState<{
    open: boolean;
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
  }>({
    open: false,
    title: "",
    message: "",
  });
  const confirmResolverRef = useRef<((result: boolean) => void) | null>(null);

  const openConfirm = (params: {
    title: string;
    message: string;
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

  useEffect(() => {
    if (!word) return;
    const forms = word.forms ?? {};
    const normalizedPhrases = normalizePhraseEntries(forms.phrases);
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
    setPhrases(normalizedPhrases);
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
        phrases: phrases
          .map((entry) => ({
            phrase: entry.phrase.trim(),
            meaning: entry.meaning.trim(),
          }))
          .filter((entry) => Boolean(entry.phrase)),
      },
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

  const saveMutation = useMutation({
    mutationFn: async () => wordApi.updateFull(word!.id, payload),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["word", String(updated.id)] });
      await queryClient.invalidateQueries({ queryKey: ["word", rawWordKey] });
      navigate(`/words/${updated.id}`);
    },
  });

  const confirmRemove = async (targetLabel: string, onAccept: () => void) => {
    const ok = await openConfirm({
      title: "削除の確認",
      message: `${targetLabel}を本当に削除しますか？`,
      confirmText: "削除する",
      cancelText: "キャンセル",
    });
    if (!ok) {
      return;
    }
    onAccept();
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
          <Link to={`/words/${word.id}`}>詳細へ戻る</Link>
        </Row>
      </Row>

      <Tabs items={EDIT_TABS} activeKey={activeTab} onChange={setActiveTab} />

      {activeTab === "basic" && (
        <Card stack>
          <h3>基本情報</h3>
          <Field label="単語">
            <input
              value={editWord}
              onChange={(e) => setEditWord(e.target.value)}
              placeholder="単語"
            />
          </Field>
          <Field label="発音記号 / IPA">
            <input
              value={phonetic}
              onChange={(e) => setPhonetic(e.target.value)}
              placeholder="発音記号 / IPA"
            />
          </Field>
          <hr className="section-divider" />
          <h3>意味・例文</h3>
          {definitions.map((def, idx) => (
            <DefinitionFormBlock
              key={def.id}
              definition={def}
              index={idx}
              onUpdate={(index, next) =>
                setDefinitions((prev) => prev.map((x, i) => (i === index ? next : x)))
              }
              onRemove={(index) =>
                void confirmRemove("この意味・例文", () =>
                  setDefinitions((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="意味・例文を追加"
            onClick={() =>
              setDefinitions((prev) => [
                ...prev,
                {
                  id: -Date.now(),
                  part_of_speech: POS_OPTIONS[0].value,
                  meaning_en: "",
                  meaning_ja: "",
                  example_en: "",
                  example_ja: "",
                  sort_order: prev.length,
                },
              ])
            }
          >
            <Plus size={18} />
          </button>
        </Card>
      )}

      {activeTab === "forms" && (
        <Card stack>
          <h3>活用形</h3>
          <Field label="三単現">
            <input value={third} onChange={(e) => setThird(e.target.value)} placeholder="三単現" />
          </Field>
          <Field label="現在分詞">
            <input
              value={presentParticiple}
              onChange={(e) => setPresentParticiple(e.target.value)}
              placeholder="現在分詞"
            />
          </Field>
          <Field label="過去形">
            <input
              value={pastTense}
              onChange={(e) => setPastTense(e.target.value)}
              placeholder="過去形"
            />
          </Field>
          <Field label="過去分詞">
            <input
              value={pastParticiple}
              onChange={(e) => setPastParticiple(e.target.value)}
              placeholder="過去分詞"
            />
          </Field>
          <Field label="複数形">
            <input value={plural} onChange={(e) => setPlural(e.target.value)} placeholder="複数形" />
          </Field>
          <Field label="比較級">
            <input
              value={comparative}
              onChange={(e) => setComparative(e.target.value)}
              placeholder="比較級"
            />
          </Field>
          <Field label="最上級">
            <input
              value={superlative}
              onChange={(e) => setSuperlative(e.target.value)}
              placeholder="最上級"
            />
          </Field>
          <Field label="不可算名詞">
            <label>
              <input
                type="checkbox"
                checked={uncountable}
                onChange={(e) => setUncountable(e.target.checked)}
              />{" "}
              不可算あり
            </label>
          </Field>
        </Card>
      )}

      {activeTab === "phrases" && (
        <Card stack>
          <h3>成句・慣用句</h3>
          {phrases.map((item, idx) => (
            <PhraseFormBlock
              key={idx}
              phraseEntry={item}
              index={idx}
              onUpdate={(index, next) =>
                setPhrases((prev) => prev.map((x, i) => (i === index ? next : x)))
              }
              onRemove={(index) =>
                void confirmRemove("この成句", () =>
                  setPhrases((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="成句を追加"
            onClick={() =>
              setPhrases((prev) => [
                ...prev,
                {
                  phrase: "",
                  meaning: "",
                },
              ])
            }
          >
            <Plus size={18} />
          </button>
        </Card>
      )}

      {activeTab === "etymology" && (
        <Card stack>
          <h3>語源</h3>
          <Field label="語源言語">
            <input
              value={originLanguage}
              onChange={(e) => setOriginLanguage(e.target.value)}
              placeholder="語源言語"
            />
          </Field>
          <Field label="語源語">
            <input
              value={originWord}
              onChange={(e) => setOriginWord(e.target.value)}
              placeholder="語源語"
            />
          </Field>
          <Field label="コアイメージ">
            <input
              value={coreImage}
              onChange={(e) => setCoreImage(e.target.value)}
              placeholder="コアイメージ"
            />
          </Field>
          <Field label="語源説明">
            <textarea
              rows={5}
              value={rawDescription}
              onChange={(e) => setRawDescription(e.target.value)}
              placeholder="語源説明"
            />
          </Field>
          <h4>語源分解</h4>
          {components.map((item, idx) => (
            <ComponentFormBlock
              key={`component-${idx}`}
              component={item}
              index={idx}
              onUpdate={(index, next) =>
                setComponents((prev) => prev.map((entry, i) => (i === index ? next : entry)))
              }
              onRemove={(index) =>
                void confirmRemove("この語源分解", () =>
                  setComponents((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="語源分解を追加"
            onClick={() =>
              setComponents((prev) => [...prev, { text: "", meaning: "", type: "root" }])
            }
          >
            <Plus size={18} />
          </button>

          <h4>意味の分岐</h4>
          {branches.map((item, idx) => (
            <BranchFormBlock
              key={`branch-${idx}`}
              branch={item}
              index={idx}
              onUpdate={(index, next) =>
                setBranches((prev) => prev.map((entry, i) => (i === index ? next : entry)))
              }
              onRemove={(index) =>
                void confirmRemove("この意味の分岐", () =>
                  setBranches((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="意味の分岐を追加"
            onClick={() => setBranches((prev) => [...prev, { label: "", meaning_en: "" }])}
          >
            <Plus size={18} />
          </button>

          <h4>語源の来歴</h4>
          {languageChain.map((item, idx) => (
            <LanguageChainFormBlock
              key={`language-chain-${idx}`}
              link={item}
              index={idx}
              onUpdate={(index, next) =>
                setLanguageChain((prev) => prev.map((entry, i) => (i === index ? next : entry)))
              }
              onRemove={(index) =>
                void confirmRemove("この語源の来歴", () =>
                  setLanguageChain((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="語源の来歴を追加"
            onClick={() =>
              setLanguageChain((prev) => [
                ...prev,
                { lang: "", lang_name: "", word: "", relation: "" },
              ])
            }
          >
            <Plus size={18} />
          </button>

          <h4>語源要素の意味</h4>
          {componentMeanings.map((item, idx) => (
            <ComponentMeaningFormBlock
              key={`component-meaning-${idx}`}
              item={item}
              index={idx}
              onUpdate={(index, next) =>
                setComponentMeanings((prev) =>
                  prev.map((entry, i) => (i === index ? next : entry)),
                )
              }
              onRemove={(index) =>
                void confirmRemove("この語源要素の意味", () =>
                  setComponentMeanings((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="語源要素の意味を追加"
            onClick={() => setComponentMeanings((prev) => [...prev, { text: "", meaning: "" }])}
          >
            <Plus size={18} />
          </button>

        </Card>
      )}

      {activeTab === "etymologyVariants" && (
        <Card stack>
          <h3>語源バリエーション</h3>
          {etymologyVariants.map((item, idx) => (
            <EtymologyVariantFormBlock
              key={`etymology-variant-${idx}`}
              variant={item}
              index={idx}
              onUpdate={(index, next) =>
                setEtymologyVariants((prev) =>
                  prev.map((entry, i) => (i === index ? next : entry)),
                )
              }
              onRemove={(index) =>
                void confirmRemove("この語源バリエーション", () =>
                  setEtymologyVariants((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="語源バリエーションを追加"
            onClick={() => setEtymologyVariants((prev) => [...prev, { label: "", excerpt: "" }])}
          >
            <Plus size={18} />
          </button>
        </Card>
      )}

      {activeTab === "derivations" && (
        <Card stack>
          <h3>派生語</h3>
          {derivations.map((item, idx) => (
            <DerivationFormBlock
              key={item.id}
              derivation={item}
              index={idx}
              onUpdate={(index, next) =>
                setDerivations((prev) => prev.map((x, i) => (i === index ? next : x)))
              }
              onRemove={(index) =>
                void confirmRemove("この派生語", () =>
                  setDerivations((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="派生語を追加"
            onClick={() =>
              setDerivations((prev) => [
                ...prev,
                {
                  id: -Date.now(),
                  derived_word: "",
                  part_of_speech: POS_OPTIONS[0].value,
                  meaning_ja: "",
                  sort_order: prev.length,
                },
              ])
            }
          >
            <Plus size={18} />
          </button>
        </Card>
      )}

      {activeTab === "related" && (
        <Card stack>
          <h3>関連語</h3>
          {relatedWords.map((item, idx) => (
            <RelatedWordFormBlock
              key={item.id}
              relatedWord={item}
              index={idx}
              onUpdate={(index, next) =>
                setRelatedWords((prev) => prev.map((x, i) => (i === index ? next : x)))
              }
              onRemove={(index) =>
                void confirmRemove("この関連語", () =>
                  setRelatedWords((prev) => prev.filter((_, i) => i !== index)),
                )
              }
            />
          ))}
          <button
            type="button"
            className="icon-button-add"
            aria-label="関連語を追加"
            onClick={() =>
              setRelatedWords((prev) => [
                ...prev,
                {
                  id: -Date.now(),
                  related_word: "",
                  relation_type: "synonym",
                  note: "",
                  linked_word_id: null,
                },
              ])
            }
          >
            <Plus size={18} />
          </button>
        </Card>
      )}

      <Row>
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending ? "保存中..." : "保存"}
        </button>
        <Link to={`/words/${word.id}`}>キャンセル</Link>
      </Row>
      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        confirmText={confirmState.confirmText}
        cancelText={confirmState.cancelText}
        onCancel={() => closeConfirm(false)}
        onConfirm={() => closeConfirm(true)}
      />
    </main>
  );
}
