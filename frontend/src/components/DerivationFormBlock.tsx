import { Field, FormBlockLayout, PosSelect } from "./atom";
import type { Derivation } from "../types";

interface DerivationFormBlockProps {
  derivation: Derivation;
  index: number;
  onUpdate: (index: number, next: Derivation) => void;
  onRemove: (index: number) => void;
}

export function DerivationFormBlock({
  derivation,
  index,
  onUpdate,
  onRemove,
}: DerivationFormBlockProps) {
  return (
    <FormBlockLayout variant="inline" onRemove={() => onRemove(index)} removeLabel="派生語を削除">
      <Field label="派生語" className="field-grow">
        <input
          value={derivation.derived_word}
          onChange={(e) => onUpdate(index, { ...derivation, derived_word: e.target.value })}
          placeholder="派生語"
        />
      </Field>
      <Field label="品詞" className="field-grow">
        <PosSelect
          value={derivation.part_of_speech}
          onChange={(value) => onUpdate(index, { ...derivation, part_of_speech: value })}
        />
      </Field>
      <Field label="意味（日本語）" className="field-grow">
        <input
          value={derivation.meaning_ja}
          onChange={(e) => onUpdate(index, { ...derivation, meaning_ja: e.target.value })}
          placeholder="意味（日本語）"
        />
      </Field>
    </FormBlockLayout>
  );
}
