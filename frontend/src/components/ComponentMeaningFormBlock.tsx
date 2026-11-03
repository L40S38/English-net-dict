import { Field, FormBlockLayout } from "./atom";
import type { ComponentMeaningItem } from "../types";

interface ComponentMeaningFormBlockProps {
  item: ComponentMeaningItem;
  index: number;
  onUpdate: (index: number, next: ComponentMeaningItem) => void;
  onRemove: (index: number) => void;
}

export function ComponentMeaningFormBlock({
  item,
  index,
  onUpdate,
  onRemove,
}: ComponentMeaningFormBlockProps) {
  return (
    <FormBlockLayout
      variant="inline"
      onRemove={() => onRemove(index)}
      removeLabel="語源要素の意味を削除"
    >
      <Field label="要素" className="field-grow">
        <input
          value={item.text}
          onChange={(e) => onUpdate(index, { ...item, text: e.target.value })}
          placeholder="例: ex-"
        />
      </Field>
      <Field label="意味" className="field-grow">
        <input
          value={item.meaning}
          onChange={(e) => onUpdate(index, { ...item, meaning: e.target.value })}
          placeholder="例: 外へ"
        />
      </Field>
    </FormBlockLayout>
  );
}
