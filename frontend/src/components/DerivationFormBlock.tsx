import { Trash2 } from "lucide-react";
import { Card, Field } from "./atom";
import { POS_OPTIONS } from "../lib/constants";
import type { Derivation } from "../types";

interface Props {
  derivation: Derivation;
  index: number;
  onUpdate: (index: number, next: Derivation) => void;
  onRemove: (index: number) => void;
}

export function DerivationFormBlock({ derivation, index, onUpdate, onRemove }: Props) {
  return (
    <Card variant="sub">
      <div className="inline-form-row">
        <Field label="派生語" className="field-grow">
          <input
            value={derivation.derived_word}
            onChange={(e) => onUpdate(index, { ...derivation, derived_word: e.target.value })}
            placeholder="派生語"
          />
        </Field>
        <Field label="品詞" className="field-grow">
          <select
            value={derivation.part_of_speech}
            onChange={(e) => onUpdate(index, { ...derivation, part_of_speech: e.target.value })}
          >
            {!POS_OPTIONS.some((option) => option.value === derivation.part_of_speech) && (
              <option value={derivation.part_of_speech}>{derivation.part_of_speech}</option>
            )}
            {POS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="意味（日本語）" className="field-grow">
          <input
            value={derivation.meaning_ja}
            onChange={(e) => onUpdate(index, { ...derivation, meaning_ja: e.target.value })}
            placeholder="意味（日本語）"
          />
        </Field>
        <button
          type="button"
          className="icon-button-delete"
          onClick={() => onRemove(index)}
          aria-label="派生語を削除"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </Card>
  );
}
