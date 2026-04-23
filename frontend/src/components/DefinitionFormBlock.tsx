import { Field, FormBlockLayout, PosSelect } from "./atom";
import type { Definition } from "../types";

interface DefinitionFormBlockProps {
  definition: Definition;
  index: number;
  onUpdate: (index: number, next: Definition) => void;
  onRemove: (index: number) => void;
  confirmRemove?: (targetLabel: string, onAccept: () => void) => Promise<void>;
}

export function DefinitionFormBlock({
  definition,
  index,
  onUpdate,
  onRemove,
  confirmRemove,
}: DefinitionFormBlockProps) {
  return (
    <FormBlockLayout
      variant="stack"
      onRemove={() => onRemove(index)}
      removeLabel="意味・例文を削除"
      confirmRemove={confirmRemove}
    >
      <Field label="品詞">
        <PosSelect
          value={definition.part_of_speech}
          onChange={(value) => onUpdate(index, { ...definition, part_of_speech: value })}
        />
      </Field>
      <Field label="英語の意味">
        <textarea
          rows={2}
          value={definition.meaning_en}
          onChange={(e) => onUpdate(index, { ...definition, meaning_en: e.target.value })}
          placeholder="英語の意味"
        />
      </Field>
      <Field label="日本語の意味">
        <textarea
          rows={2}
          value={definition.meaning_ja}
          onChange={(e) => onUpdate(index, { ...definition, meaning_ja: e.target.value })}
          placeholder="日本語の意味"
        />
      </Field>
      <Field label="例文（英語）">
        <textarea
          rows={2}
          value={definition.example_en}
          onChange={(e) => onUpdate(index, { ...definition, example_en: e.target.value })}
          placeholder="例文（英語）"
        />
      </Field>
      <Field label="例文（日本語訳）">
        <textarea
          rows={2}
          value={definition.example_ja}
          onChange={(e) => onUpdate(index, { ...definition, example_ja: e.target.value })}
          placeholder="例文（日本語訳）"
        />
      </Field>
    </FormBlockLayout>
  );
}
