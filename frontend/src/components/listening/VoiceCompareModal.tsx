import { useEffect } from "react";

import { VoiceComparePanel } from "./VoiceComparePanel";
import type { ListeningLine } from "../../types";

interface VoiceCompareModalProps {
  line: ListeningLine | null;
  onClose: () => void;
  onAudioGenerated?: () => void;
}

export function VoiceCompareModal({ line, onClose, onAudioGenerated }: VoiceCompareModalProps) {
  useEffect(() => {
    if (!line) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [line, onClose]);

  if (!line) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={onClose} aria-hidden="true">
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-label="声の聴き比べ"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 className="modal-title">声の聴き比べ</h3>
        <VoiceComparePanel line={line} onAudioGenerated={onAudioGenerated} />
        <div className="modal-actions">
          <button type="button" className="modal-cancel" onClick={onClose}>
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
}
