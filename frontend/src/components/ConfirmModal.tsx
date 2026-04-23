import { useEffect } from "react";

type Props = {
  open: boolean;
  title: string;
  message: string;
  /** 確定のみ（エラー表示など）。キャンセルボタンを出さない */
  variant?: "confirm" | "alert";
  /** danger は削除などの破壊的操作向け */
  confirmVariant?: "default" | "danger";
  confirmText?: string;
  cancelText?: string;
  /** 真のとき操作ボタンを無効化し、オーバーレイ・Esc による閉じるも無効 */
  disableActions?: boolean;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
};

export function ConfirmModal({
  open,
  title,
  message,
  variant = "confirm",
  confirmVariant = "default",
  confirmText = "OK",
  cancelText = "キャンセル",
  disableActions = false,
  onConfirm,
  onCancel,
}: Props) {
  const confirmClassName = confirmVariant === "danger" ? "button-delete" : "modal-confirm";

  useEffect(() => {
    if (!open) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !disableActions) {
        onCancel();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onCancel, disableActions]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="modal-overlay"
      onClick={() => {
        if (!disableActions) {
          onCancel();
        }
      }}
      aria-hidden="true"
    >
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
              <button type="button" className="modal-cancel" onClick={onCancel} disabled={disableActions}>
                {cancelText}
              </button>
              <button
                type="button"
                className={confirmClassName}
                onClick={() => void onConfirm()}
                disabled={disableActions}
              >
                {confirmText}
              </button>
            </>
          ) : (
            <button
              type="button"
              className={confirmClassName}
              onClick={() => void onConfirm()}
              disabled={disableActions}
            >
              {confirmText}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
