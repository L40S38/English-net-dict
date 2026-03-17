import { Card, Field } from "./atom";
import { POS_OPTIONS } from "../lib/constants";
import type { Definition } from "../types";

interface Props {
  definition: Definition;
  index: number;
  onUpdate: (index: number, next: Definition) => void;
  onRemove: (index: number) => void;
}

export function DefinitionFormBlock({ definition, index, onUpdate, onRemove }: Props) {
  return (
    <Card variant="sub" stack>
      <Field label="品詞">
        <select
          value={definition.part_of_speech}
          onChange={(e) => onUpdate(index, { ...definition, part_of_speech: e.target.value })}
        >
          {!POS_OPTIONS.some((option) => option.value === definition.part_of_speech) && (
            <option value={definition.part_of_speech}>{definition.part_of_speech}</option>
          )}
          {POS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
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
      <button type="button" onClick={() => onRemove(index)}>
        削除
      </button>
    </Card>
  );
}
