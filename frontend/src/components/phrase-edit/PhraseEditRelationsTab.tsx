import { Plus } from "lucide-react";

import { FormBlockLayout, Card, Field } from "../atom";

export type PhraseRelationType = "synonym" | "antonym" | "confusable" | "cognate" | "phrase";

export interface PhraseRelatedItem {
  id: number;
  related_word: string;
  relation_type: PhraseRelationType;
  note: string;
}

interface PhraseEditRelationsTabProps {
  relatedItems: PhraseRelatedItem[];
  setRelatedItems: React.Dispatch<React.SetStateAction<PhraseRelatedItem[]>>;
  confirmRemove: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

const PHRASE_RELATION_TYPE_LABELS: Record<PhraseRelationType, string> = {
  synonym: "類義語",
  antonym: "対義語",
  confusable: "紛らわしい語",
  cognate: "同語源",
  phrase: "成句・慣用句",
};

const RELATION_TYPE_OPTIONS: PhraseRelationType[] = [
  "synonym",
  "antonym",
  "confusable",
  "cognate",
  "phrase",
];

export function PhraseEditRelationsTab({
  relatedItems,
  setRelatedItems,
  confirmRemove,
}: PhraseEditRelationsTabProps) {
  const updateAt = (index: number, updater: (current: PhraseRelatedItem) => PhraseRelatedItem) => {
    setRelatedItems((prev) => prev.map((item, idx) => (idx === index ? updater(item) : item)));
  };

  const removeAt = (index: number) => {
    setRelatedItems((prev) => prev.filter((_, idx) => idx !== index));
  };

  const addEntry = () => {
    setRelatedItems((prev) => [
      ...prev,
      {
        id: -Date.now(),
        related_word: "",
        relation_type: "synonym",
        note: "",
      },
    ]);
  };

  return (
    <Card stack>
      <h3>関連語</h3>
      {relatedItems.map((item, idx) => (
        <FormBlockLayout
          key={`${item.id}-${idx}`}
          variant="inline"
          onRemove={() => void confirmRemove("この関連語", () => removeAt(idx))}
          removeLabel="関連語を削除"
        >
          <Field label="単語/熟語" className="field-grow">
            <input
              value={item.related_word}
              onChange={(event) =>
                updateAt(idx, (current) => ({ ...current, related_word: event.target.value }))
              }
              placeholder="単語/熟語"
            />
          </Field>
          <Field label="関連タイプ" className="field-grow">
            <select
              value={item.relation_type}
              onChange={(event) =>
                updateAt(idx, (current) => ({
                  ...current,
                  relation_type: event.target.value as PhraseRelationType,
                }))
              }
            >
              {RELATION_TYPE_OPTIONS.map((type) => (
                <option key={type} value={type}>
                  {PHRASE_RELATION_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="補足メモ" className="field-grow">
            <input
              value={item.note}
              onChange={(event) =>
                updateAt(idx, (current) => ({ ...current, note: event.target.value }))
              }
              placeholder="補足メモ"
            />
          </Field>
        </FormBlockLayout>
      ))}
      <button type="button" className="icon-button-add" aria-label="関連語を追加" onClick={addEntry}>
        <Plus size={18} />
      </button>
    </Card>
  );
}
