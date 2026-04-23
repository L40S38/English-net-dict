import { Card, Muted } from "../atom";

interface GroupEditBulkTabProps {
  bulkText: string;
  onChangeBulkText: (value: string) => void;
  bulkFlowError: string | null;
  isBulkWordFlowPending: boolean;
  bulkFlowProgress: { completed: number; total: number } | null;
  bulkProgressPercent: number;
  onCheckAndOpenConfirm: () => void;
  bulkMissing: { words: string[]; phrases: string[] };
}

export function GroupEditBulkTab({
  bulkText,
  onChangeBulkText,
  bulkFlowError,
  isBulkWordFlowPending,
  bulkFlowProgress,
  bulkProgressPercent,
  onCheckAndOpenConfirm,
  bulkMissing,
}: GroupEditBulkTabProps) {
  return (
    <Card stack>
      <h3>単語一括追加</h3>
      <label>
        <small>1行1単語/熟語</small>
        <textarea
          rows={5}
          value={bulkText}
          onChange={(event) => onChangeBulkText(event.target.value)}
          placeholder="例: apple&#10;take off&#10;ASAP"
        />
      </label>
      {bulkFlowError && (
        <p role="alert" style={{ color: "#b91c1c", margin: "0.25rem 0 0" }}>
          {bulkFlowError}
        </p>
      )}
      {isBulkWordFlowPending && bulkFlowProgress && (
        <div className="bulk-progress" aria-live="polite">
          <div className="bulk-progress-label">
            進捗: {bulkFlowProgress.completed} / {bulkFlowProgress.total} ({bulkProgressPercent}%)
          </div>
          <div
            className="bulk-progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={bulkProgressPercent}
          >
            <div className="bulk-progress-fill" style={{ width: `${bulkProgressPercent}%` }} />
          </div>
        </div>
      )}
      <button type="button" disabled={isBulkWordFlowPending} onClick={onCheckAndOpenConfirm}>
        {isBulkWordFlowPending
          ? `一括追加中... (${bulkFlowProgress?.completed ?? 0}/${bulkFlowProgress?.total ?? 0})`
          : "確認して追加"}
      </button>
      {(bulkMissing.words.length > 0 || bulkMissing.phrases.length > 0) && (
        <Muted as="p">
          未登録:
          {bulkMissing.words.length > 0 ? ` 単語(${bulkMissing.words.join(", ")})` : ""}
          {bulkMissing.phrases.length > 0 ? ` 熟語(${bulkMissing.phrases.join(", ")})` : ""}
        </Muted>
      )}
    </Card>
  );
}
