import { Trash2 } from "lucide-react";
import { Card, Field } from "./atom";
import type { Phrase } from "../types";

interface Props {
  phraseEntry: Pick<Phrase, "text" | "meaning">;
  index: number;
  onUpdate: (index: number, next: Pick<Phrase, "text" | "meaning">) => void;
  onRemove: (index: number) => void;
}

export function PhraseFormBlock({ phraseEntry, index, onUpdate, onRemove }: Props) {
  return (
    <Card variant="sub">
      <div className="inline-form-row">
        <Field label="成句・慣用句" className="field-grow">
          <input
            value={phraseEntry.text}
            onChange={(e) => onUpdate(index, { ...phraseEntry, text: e.target.value })}
            placeholder="成句・慣用句"
          />
        </Field>
        <Field label="意味" className="field-grow">
          <input
            value={phraseEntry.meaning}
            onChange={(e) => onUpdate(index, { ...phraseEntry, meaning: e.target.value })}
            placeholder="意味"
          />
        </Field>
        <button
          type="button"
          className="icon-button-delete"
          onClick={() => onRemove(index)}
          aria-label="成句を削除"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </Card>
  );
}
