import { Trash2 } from "lucide-react";

import { Card } from "./Card";

interface FormBlockLayoutProps {
  variant?: "inline" | "stack";
  onRemove: () => void;
  removeLabel: string;
  children: React.ReactNode;
}

export function FormBlockLayout({
  variant = "inline",
  onRemove,
  removeLabel,
  children,
}: FormBlockLayoutProps) {
  const isInline = variant === "inline";
  return (
    <Card variant="sub" stack={!isInline}>
      {isInline ? <div className="inline-form-row">{children}</div> : children}
      <button
        type="button"
        className={isInline ? "icon-button-delete" : undefined}
        onClick={onRemove}
        aria-label={removeLabel}
      >
        {isInline ? <Trash2 size={16} /> : "削除"}
      </button>
    </Card>
  );
}
