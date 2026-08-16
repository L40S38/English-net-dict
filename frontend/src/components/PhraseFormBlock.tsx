import { Field, FormBlockLayout } from "./atom";
import type { Phrase } from "../types";

interface PhraseFormBlockProps {
  phraseEntry: Pick<Phrase, "text" | "meaning">;
  index: number;
  onUpdate: (index: number, next: Pick<Phrase, "text" | "meaning">) => void;
  onRemove: (index: number) => void;
}

export function PhraseFormBlock({ phraseEntry, index, onUpdate, onRemove }: PhraseFormBlockProps) {
  return (
    <FormBlockLayout variant="inline" onRemove={() => onRemove(index)} removeLabel="成句を削除">
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
    </FormBlockLayout>
  );
}
