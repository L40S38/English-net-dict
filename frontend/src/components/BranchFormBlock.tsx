import { Trash2 } from "lucide-react";
import { Card, Field } from "./atom";
import type { EtymologyBranch } from "../types";

interface Props {
  branch: EtymologyBranch;
  index: number;
  onUpdate: (index: number, next: EtymologyBranch) => void;
  onRemove: (index: number) => void;
}

export function BranchFormBlock({ branch, index, onUpdate, onRemove }: Props) {
  return (
    <Card variant="sub">
      <div className="inline-form-row">
        <Field label="分岐ラベル" className="field-grow">
          <input
            value={branch.label}
            onChange={(e) => onUpdate(index, { ...branch, label: e.target.value })}
            placeholder="例: unfold"
          />
        </Field>
        <Field label="意味（英語）" className="field-grow">
          <input
            value={branch.meaning_en ?? ""}
            onChange={(e) =>
              onUpdate(index, { ...branch, meaning_en: e.target.value || undefined })
            }
            placeholder="例: to open out"
          />
        </Field>
        <button
          type="button"
          className="icon-button-delete"
          onClick={() => onRemove(index)}
          aria-label="意味の分岐を削除"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </Card>
  );
}
