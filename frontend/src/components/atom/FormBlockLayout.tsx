import { Trash2 } from "lucide-react";

import { Card } from "./Card";

interface FormBlockLayoutProps {
  variant?: "inline" | "stack";
  onRemove: () => void;
  removeLabel: string;
  confirmRemove?: (targetLabel: string, onAccept: () => void) => Promise<void>;
  children: React.ReactNode;
}

export function FormBlockLayout({
  variant = "inline",
  onRemove,
  removeLabel,
  confirmRemove,
  children,
}: FormBlockLayoutProps) {
  const isInline = variant === "inline";
  if (isInline) {
    return (
      <Card variant="sub">
        <div className="inline-form-row">
          {children}
          <button
            type="button"
            className="icon-button-delete"
            onClick={onRemove}
            aria-label={removeLabel}
          >
            <Trash2 size={16} />
          </button>
        </div>
      </Card>
    );
  }
  return (
    <Card variant="sub" stack>
      {children}
      <button
        type="button"
        className="button-delete"
        onClick={() => {
          if (!confirmRemove) {
            onRemove();
            return;
          }
          void confirmRemove("この意味・例文", onRemove);
        }}
        aria-label={removeLabel}
      >
        削除
      </button>
    </Card>
  );
}
