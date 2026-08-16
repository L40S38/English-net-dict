import { Field, FormBlockLayout } from "./atom";
import { RELATION_TYPE_LABELS } from "../lib/constants";
import type { RelatedWord, RelationType } from "../types";

interface RelatedWordFormBlockProps {
  relatedWord: RelatedWord;
  index: number;
  onUpdate: (index: number, next: RelatedWord) => void;
  onRemove: (index: number) => void;
}

export function RelatedWordFormBlock({
  relatedWord,
  index,
  onUpdate,
  onRemove,
}: RelatedWordFormBlockProps) {
  return (
    <FormBlockLayout variant="inline" onRemove={() => onRemove(index)} removeLabel="関連語を削除">
      <Field label="関連語" className="field-grow">
        <input
          value={relatedWord.related_word}
          onChange={(e) => onUpdate(index, { ...relatedWord, related_word: e.target.value })}
          placeholder="関連語"
        />
      </Field>
      <Field label="関連タイプ" className="field-grow">
        <select
          value={relatedWord.relation_type}
          onChange={(e) =>
            onUpdate(index, {
              ...relatedWord,
              relation_type: e.target.value as RelationType,
            })
          }
        >
          {(Object.keys(RELATION_TYPE_LABELS) as RelationType[]).map((type) => (
            <option key={type} value={type}>
              {RELATION_TYPE_LABELS[type]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="補足メモ" className="field-grow">
        <input
          value={relatedWord.note}
          onChange={(e) => onUpdate(index, { ...relatedWord, note: e.target.value })}
          placeholder="補足メモ"
        />
      </Field>
    </FormBlockLayout>
  );
}
