import type { ReactNode } from "react";

import { Card, Muted, Row, Stack } from "../atom";

interface CandidateSectionProps {
  title: string;
  page: number;
  total: number;
  pageSize: number;
  selectedCount?: number;
  loading?: boolean;
  emptyMessage?: string;
  canPrev?: boolean;
  canNext?: boolean;
  onPrevPage?: () => void;
  onNextPage?: () => void;
  onSelectAllPage?: () => void;
  onClearSelection?: () => void;
  onConfirmSelection?: () => void;
  confirmLabel?: string;
  confirmDisabled?: boolean;
  children: ReactNode;
}

export function CandidateSection({
  title,
  page,
  total,
  pageSize,
  selectedCount = 0,
  loading = false,
  emptyMessage = "候補はありません。",
  canPrev,
  canNext,
  onPrevPage,
  onNextPage,
  onSelectAllPage,
  onClearSelection,
  onConfirmSelection,
  confirmLabel = "選択項目を追加",
  confirmDisabled = false,
  children,
}: CandidateSectionProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const prevEnabled = Boolean(onPrevPage) && (canPrev ?? page > 1);
  const nextEnabled = Boolean(onNextPage) && (canNext ?? page < totalPages);

  return (
    <Card stack>
      <Row justify="between">
        <h3>{title}</h3>
        <Muted as="span">
          {total} 件 / {page} / {totalPages} ページ
        </Muted>
      </Row>

      <Row>
        {onSelectAllPage ? (
          <button type="button" onClick={onSelectAllPage} disabled={loading}>
            このページを全選択
          </button>
        ) : null}
        {onClearSelection ? (
          <button type="button" className="modal-cancel" onClick={onClearSelection} disabled={loading || selectedCount === 0}>
            選択解除
          </button>
        ) : null}
        {onConfirmSelection ? (
          <button type="button" onClick={onConfirmSelection} disabled={loading || confirmDisabled || selectedCount === 0}>
            {confirmLabel}
          </button>
        ) : null}
      </Row>

      {loading ? <Muted as="p">候補を読み込み中...</Muted> : null}
      {!loading && total === 0 ? <Muted as="p">{emptyMessage}</Muted> : null}

      {!loading && total > 0 ? <Stack>{children}</Stack> : null}

      <Row>
        <button type="button" className="modal-cancel" onClick={onPrevPage} disabled={!prevEnabled || loading}>
          前へ
        </button>
        <button type="button" className="modal-cancel" onClick={onNextPage} disabled={!nextEnabled || loading}>
          次へ
        </button>
      </Row>
    </Card>
  );
}
