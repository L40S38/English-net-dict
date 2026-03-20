import { useEffect } from "react";

type Props = {
  open: boolean;
  title: string;
  message: string;
  /** 確定のみ（エラー表示など）。キャンセルボタンを出さない */
  variant?: "confirm" | "alert";
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
};

export function ConfirmModal({
  open,
  title,
  message,
  variant = "confirm",
  confirmText = "OK",
  cancelText = "キャンセル",
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onCancel();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onCancel]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onCancel} aria-hidden="true">
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <h3 className="modal-title">{title}</h3>
        <p className="modal-message">{message}</p>
        <div className="modal-actions">
          {variant === "confirm" ? (
            <>
              <button type="button" className="modal-cancel" onClick={onCancel}>
                {cancelText}
              </button>
              <button type="button" className="modal-confirm" onClick={() => void onConfirm()}>
                {confirmText}
              </button>
            </>
          ) : (
            <button type="button" className="modal-confirm" onClick={() => void onConfirm()}>
              {confirmText}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
