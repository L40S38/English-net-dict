import { Field, PosSelect, Row, Stack } from "../atom";
import type { PhraseDefinition } from "../../types";

interface PhraseEditDefinitionsTabProps {
  definitions: PhraseDefinition[];
  setDefinitions: (next: PhraseDefinition[]) => void;
}

function createDefinition(sortOrder: number): PhraseDefinition {
  return {
    id: -(sortOrder + 1),
    part_of_speech: "phrase",
    meaning_en: "",
    meaning_ja: "",
    example_en: "",
    example_ja: "",
    sort_order: sortOrder,
  };
}

export function PhraseEditDefinitionsTab({ definitions, setDefinitions }: PhraseEditDefinitionsTabProps) {
  const updateAt = (index: number, updater: (item: PhraseDefinition) => PhraseDefinition) => {
    setDefinitions(definitions.map((item, idx) => (idx === index ? updater(item) : item)));
  };
  return (
    <Stack>
      {definitions.map((item, idx) => (
        <Field key={`${item.id}-${idx}`} label={`定義 ${idx + 1}`}>
          <Stack>
            <PosSelect
              value={item.part_of_speech}
              onChange={(value) => updateAt(idx, (current) => ({ ...current, part_of_speech: value }))}
            />
            <input
              placeholder="英語の意味"
              value={item.meaning_en}
              onChange={(event) =>
                updateAt(idx, (current) => ({ ...current, meaning_en: event.target.value }))
              }
            />
            <input
              placeholder="日本語の意味"
              value={item.meaning_ja}
              onChange={(event) =>
                updateAt(idx, (current) => ({ ...current, meaning_ja: event.target.value }))
              }
            />
            <textarea
              rows={2}
              placeholder="英語の例文"
              value={item.example_en}
              onChange={(event) =>
                updateAt(idx, (current) => ({ ...current, example_en: event.target.value }))
              }
            />
            <textarea
              rows={2}
              placeholder="日本語の例文"
              value={item.example_ja}
              onChange={(event) =>
                updateAt(idx, (current) => ({ ...current, example_ja: event.target.value }))
              }
            />
            <Row>
              <button
                type="button"
                className="modal-cancel"
                onClick={() => setDefinitions(definitions.filter((_, index) => index !== idx))}
              >
                削除
              </button>
            </Row>
          </Stack>
        </Field>
      ))}
      <button type="button" onClick={() => setDefinitions([...definitions, createDefinition(definitions.length)])}>
        定義を追加
      </button>
    </Stack>
  );
}
