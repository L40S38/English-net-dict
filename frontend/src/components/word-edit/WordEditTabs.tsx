import { Plus } from "lucide-react";

import { BranchFormBlock } from "../BranchFormBlock";
import { ComponentFormBlock } from "../ComponentFormBlock";
import { ComponentMeaningFormBlock } from "../ComponentMeaningFormBlock";
import { DefinitionFormBlock } from "../DefinitionFormBlock";
import { DerivationFormBlock } from "../DerivationFormBlock";
import { EtymologyVariantFormBlock } from "../EtymologyVariantFormBlock";
import { LanguageChainFormBlock } from "../LanguageChainFormBlock";
import { PhraseFormBlock } from "../PhraseFormBlock";
import { RelatedWordFormBlock } from "../RelatedWordFormBlock";
import { Card, Field } from "../atom";
import { POS_OPTIONS } from "../../lib/constants";
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
} from "../../types";

interface WordEditBasicTabProps {
  editWord: string;
  phonetic: string;
  definitions: Word["definitions"];
  setEditWord: (value: string) => void;
  setPhonetic: (value: string) => void;
  setDefinitions: React.Dispatch<React.SetStateAction<Word["definitions"]>>;
  confirmRemove: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

export function WordEditBasicTab({
  editWord,
  phonetic,
  definitions,
  setEditWord,
  setPhonetic,
  setDefinitions,
  confirmRemove,
}: WordEditBasicTabProps) {
  return (
    <Card stack>
      <h3>基本情報</h3>
      <Field label="単語">
        <input value={editWord} onChange={(e) => setEditWord(e.target.value)} placeholder="単語" />
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
  );
}

interface WordEditFormsTabProps {
  third: string;
  presentParticiple: string;
  pastTense: string;
  pastParticiple: string;
  plural: string;
  comparative: string;
  superlative: string;
  uncountable: boolean;
  setThird: (value: string) => void;
  setPresentParticiple: (value: string) => void;
  setPastTense: (value: string) => void;
  setPastParticiple: (value: string) => void;
  setPlural: (value: string) => void;
  setComparative: (value: string) => void;
  setSuperlative: (value: string) => void;
  setUncountable: (value: boolean) => void;
}

export function WordEditFormsTab(props: WordEditFormsTabProps) {
  const {
    third,
    presentParticiple,
    pastTense,
    pastParticiple,
    plural,
    comparative,
    superlative,
    uncountable,
    setThird,
    setPresentParticiple,
    setPastTense,
    setPastParticiple,
    setPlural,
    setComparative,
    setSuperlative,
    setUncountable,
  } = props;
  return (
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
  );
}

interface WordEditPhrasesTabProps {
  phrases: Array<Pick<Phrase, "text" | "meaning">>;
  setPhrases: React.Dispatch<React.SetStateAction<Array<Pick<Phrase, "text" | "meaning">>>>;
  confirmRemove: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

export function WordEditPhrasesTab({
  phrases,
  setPhrases,
  confirmRemove,
}: WordEditPhrasesTabProps) {
  return (
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
        onClick={() => setPhrases((prev) => [...prev, { text: "", meaning: "" }])}
      >
        <Plus size={18} />
      </button>
    </Card>
  );
}

interface WordEditEtymologyTabProps {
  originLanguage: string;
  originWord: string;
  coreImage: string;
  rawDescription: string;
  components: EtymologyComponent[];
  branches: EtymologyBranch[];
  languageChain: LanguageChainLink[];
  componentMeanings: ComponentMeaningItem[];
  setOriginLanguage: (value: string) => void;
  setOriginWord: (value: string) => void;
  setCoreImage: (value: string) => void;
  setRawDescription: (value: string) => void;
  setComponents: React.Dispatch<React.SetStateAction<EtymologyComponent[]>>;
  setBranches: React.Dispatch<React.SetStateAction<EtymologyBranch[]>>;
  setLanguageChain: React.Dispatch<React.SetStateAction<LanguageChainLink[]>>;
  setComponentMeanings: React.Dispatch<React.SetStateAction<ComponentMeaningItem[]>>;
  confirmRemove: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

export function WordEditEtymologyTab(props: WordEditEtymologyTabProps) {
  const {
    originLanguage,
    originWord,
    coreImage,
    rawDescription,
    components,
    branches,
    languageChain,
    componentMeanings,
    setOriginLanguage,
    setOriginWord,
    setCoreImage,
    setRawDescription,
    setComponents,
    setBranches,
    setLanguageChain,
    setComponentMeanings,
    confirmRemove,
  } = props;
  return (
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
        onClick={() => setComponents((prev) => [...prev, { text: "", meaning: "", type: "root" }])}
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
          setLanguageChain((prev) => [...prev, { lang: "", lang_name: "", word: "", relation: "" }])
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
            setComponentMeanings((prev) => prev.map((entry, i) => (i === index ? next : entry)))
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
  );
}

interface WordEditVariantsTabProps {
  etymologyVariants: EtymologyVariant[];
  setEtymologyVariants: React.Dispatch<React.SetStateAction<EtymologyVariant[]>>;
  confirmRemove: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

export function WordEditVariantsTab({
  etymologyVariants,
  setEtymologyVariants,
  confirmRemove,
}: WordEditVariantsTabProps) {
  return (
    <Card stack>
      <h3>語源バリエーション</h3>
      {etymologyVariants.map((item, idx) => (
        <EtymologyVariantFormBlock
          key={`etymology-variant-${idx}`}
          variant={item}
          index={idx}
          onUpdate={(index, next) =>
            setEtymologyVariants((prev) => prev.map((entry, i) => (i === index ? next : entry)))
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
  );
}

interface WordEditDerivationsTabProps {
  derivations: Derivation[];
  setDerivations: React.Dispatch<React.SetStateAction<Derivation[]>>;
  confirmRemove: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

export function WordEditDerivationsTab({
  derivations,
  setDerivations,
  confirmRemove,
}: WordEditDerivationsTabProps) {
  return (
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
  );
}

interface WordEditRelatedTabProps {
  relatedWords: RelatedWord[];
  setRelatedWords: React.Dispatch<React.SetStateAction<RelatedWord[]>>;
  confirmRemove: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

export function WordEditRelatedTab({
  relatedWords,
  setRelatedWords,
  confirmRemove,
}: WordEditRelatedTabProps) {
  return (
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
  );
}
