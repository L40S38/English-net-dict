import { useState } from "react";
import { Card } from "./atom";

interface Props {
  onImport: (words: string[]) => Promise<boolean | void> | boolean | void;
  disabled?: boolean;
  loading?: boolean;
  progress?: { completed: number; total: number } | null;
}

export function BulkImport({
  onImport,
  disabled = false,
  loading = false,
  progress = null,
}: Props) {
  const [text, setText] = useState("");
  const progressPercent =
    progress && progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;

  return (
    <Card stack>
      <h3>一括インポート</h3>
      <textarea
        rows={5}
        placeholder="1行1単語で入力"
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled}
      />
      <button
        disabled={disabled}
        onClick={async () => {
          const words = text
            .split(/\r?\n/)
            .map((x) => x.trim())
            .filter(Boolean);
          if (words.length === 0) return;
          const result = await onImport(words);
          if (result !== false) {
            setText("");
          }
        }}
      >
        {loading
          ? `取り込み中... (${progress?.completed ?? 0}/${progress?.total ?? 0})`
          : "取り込み"}
      </button>
      {loading && progress && (
        <div className="bulk-progress" aria-live="polite">
          <div className="bulk-progress-label">
            進捗: {progress.completed} / {progress.total} ({progressPercent}%)
          </div>
          <div
            className="bulk-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progressPercent}
          >
            <div className="bulk-progress-fill" style={{ width: `${progressPercent}%` }} />
          </div>
        </div>
      )}
    </Card>
  );
}
