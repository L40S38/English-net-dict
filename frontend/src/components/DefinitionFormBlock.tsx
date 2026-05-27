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
  const examples = definition.examples ?? [];

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
      <Field label="例文（複数）">
        {examples.map((example, exampleIndex) => (
          <div key={`${definition.id}-${exampleIndex}`} style={{ marginBottom: "0.75rem" }}>
            <textarea
              rows={2}
              value={example.example_en}
              onChange={(e) =>
                onUpdate(index, {
                  ...definition,
                  examples: examples.map((x, i) =>
                    i === exampleIndex ? { ...x, example_en: e.target.value } : x,
                  ),
                })
              }
              placeholder="例文（英語）"
            />
            <textarea
              rows={2}
              value={example.example_ja}
              onChange={(e) =>
                onUpdate(index, {
                  ...definition,
                  examples: examples.map((x, i) =>
                    i === exampleIndex ? { ...x, example_ja: e.target.value } : x,
                  ),
                })
              }
              placeholder="例文（日本語訳）"
            />
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem" }}>
              <button
                type="button"
                onClick={() => {
                  if (exampleIndex === 0) return;
                  const next = [...examples];
                  const [current] = next.splice(exampleIndex, 1);
                  next.splice(exampleIndex - 1, 0, current);
                  onUpdate(index, {
                    ...definition,
                    examples: next.map((x, i) => ({ ...x, sort_order: i })),
                  });
                }}
              >
                ↑
              </button>
              <button
                type="button"
                onClick={() => {
                  if (exampleIndex >= examples.length - 1) return;
                  const next = [...examples];
                  const [current] = next.splice(exampleIndex, 1);
                  next.splice(exampleIndex + 1, 0, current);
                  onUpdate(index, {
                    ...definition,
                    examples: next.map((x, i) => ({ ...x, sort_order: i })),
                  });
                }}
              >
                ↓
              </button>
              <button
                type="button"
                onClick={() =>
                  onUpdate(index, {
                    ...definition,
                    examples: examples.filter((_, i) => i !== exampleIndex).map((x, i) => ({
                      ...x,
                      sort_order: i,
                    })),
                  })
                }
              >
                削除
              </button>
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={() =>
            onUpdate(index, {
              ...definition,
              examples: [
                ...examples,
                { example_en: "", example_ja: "", sort_order: examples.length },
              ],
            })
          }
        >
          例文を追加
        </button>
      </Field>
    </FormBlockLayout>
  );
}
