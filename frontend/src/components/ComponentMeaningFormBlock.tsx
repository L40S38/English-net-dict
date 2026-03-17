import { Trash2 } from "lucide-react";
import { Card, Field } from "./atom";

export interface ComponentMeaningItem {
  text: string;
  meaning: string;
}

interface Props {
  item: ComponentMeaningItem;
  index: number;
  onUpdate: (index: number, next: ComponentMeaningItem) => void;
  onRemove: (index: number) => void;
}

export function ComponentMeaningFormBlock({ item, index, onUpdate, onRemove }: Props) {
  return (
    <Card variant="sub">
      <div className="inline-form-row">
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
        <button
          type="button"
          className="icon-button-delete"
          onClick={() => onRemove(index)}
          aria-label="語源要素の意味を削除"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </Card>
  );
}
