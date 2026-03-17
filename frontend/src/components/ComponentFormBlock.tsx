import { Trash2 } from "lucide-react";
import { Card, Field } from "./atom";
import type { EtymologyComponent } from "../types";

const COMPONENT_TYPE_OPTIONS = [
  { value: "root", label: "語根" },
  { value: "prefix", label: "接頭辞" },
  { value: "suffix", label: "接尾辞" },
] as const;

interface Props {
  component: EtymologyComponent;
  index: number;
  onUpdate: (index: number, next: EtymologyComponent) => void;
  onRemove: (index: number) => void;
}

export function ComponentFormBlock({ component, index, onUpdate, onRemove }: Props) {
  return (
    <Card variant="sub">
      <div className="inline-form-row">
        <Field label="要素" className="field-grow">
          <input
            value={component.text}
            onChange={(e) => onUpdate(index, { ...component, text: e.target.value })}
            placeholder="例: ex-"
          />
        </Field>
        <Field label="意味" className="field-grow">
          <input
            value={component.meaning}
            onChange={(e) => onUpdate(index, { ...component, meaning: e.target.value })}
            placeholder="例: 外へ"
          />
        </Field>
        <Field label="種別" className="field-grow">
          <select
            value={component.type ?? "root"}
            onChange={(e) => onUpdate(index, { ...component, type: e.target.value })}
          >
            {component.type &&
              !COMPONENT_TYPE_OPTIONS.some((option) => option.value === component.type) && (
                <option value={component.type}>{component.type}</option>
              )}
            {COMPONENT_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <button
          type="button"
          className="icon-button-delete"
          onClick={() => onRemove(index)}
          aria-label="語源要素を削除"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </Card>
  );
}
