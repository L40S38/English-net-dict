import { useEffect, useMemo, useState } from "react";

import { INFLECTION_LABELS } from "../lib/constants";
import type { InflectionAction } from "../types";

export interface InflectionBatchItem {
  word: string;
  selectedLemma?: string | null;
  selectedSpelling?: string | null;
  lemmaResolution?: "direct" | "resolved_from_inflection" | "manual" | null;
  selectedInflectionType?: string | null;
  lemmaCandidates?: Array<{
    lemma: string;
    lemmaWordId?: number | null;
    inflectionType?: string | null;
  }>;
  spellingCandidates?: Array<{
    spelling: string;
    source?: string | null;
    selectedLemma?: string | null;
    lemmaResolution?: "direct" | "resolved_from_inflection" | "manual" | null;
    lemmaCandidates?: Array<{
      lemma: string;
      lemmaWordId?: number | null;
      inflectionType?: string | null;
    }>;
  }>;
  suggestion: InflectionAction;
}

export interface InflectionBatchDecision {
  action: InflectionAction;
  lemma: string | null;
  spelling: string | null;
}

interface InflectionBatchModalProps {
  open: boolean;
  title?: string;
  items: InflectionBatchItem[];
  onClose: () => void;
  onConfirm: (decisions: Record<string, InflectionBatchDecision>) => void;
}

export function InflectionBatchModal({
  open,
  title = "活用形の一括確認",
  items,
  onClose,
  onConfirm,
}: InflectionBatchModalProps) {
  const getLemmaCandidatesBySpelling = (
    item: InflectionBatchItem,
    selectedSpelling: string | null,
  ): NonNullable<InflectionBatchItem["lemmaCandidates"]> => {
    if (!selectedSpelling) {
      return item.lemmaCandidates ?? [];
    }
    const matched = (item.spellingCandidates ?? []).find((entry) => entry.spelling === selectedSpelling);
    if (matched?.lemmaCandidates && matched.lemmaCandidates.length > 0) {
      return matched.lemmaCandidates;
    }
    return item.lemmaCandidates ?? [];
  };

  const initialDecisions = useMemo<Record<string, InflectionBatchDecision>>(() => {
    const next: Record<string, InflectionBatchDecision> = {};
    for (const item of items) {
      const defaultSpelling =
        item.selectedSpelling ?? item.spellingCandidates?.[0]?.spelling ?? null;
      const defaultLemmaCandidates = getLemmaCandidatesBySpelling(item, defaultSpelling);
      next[item.word] = {
        action: item.suggestion,
        lemma: item.selectedLemma ?? defaultLemmaCandidates?.[0]?.lemma ?? null,
        spelling: defaultSpelling,
      };
    }
    return next;
  }, [items]);

  const [decisions, setDecisions] =
    useState<Record<string, InflectionBatchDecision>>(initialDecisions);

  useEffect(() => {
    setDecisions(initialDecisions);
  }, [initialDecisions]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose} aria-hidden="true">
      <div
        className="modal-panel modal-panel-lg"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="modal-title">{title}</h3>
        <p className="modal-message">候補 {items.length} 件をまとめて確認します。</p>

        <div className="inflection-batch-list">
          {items.map((item) => {
            const inflectionLabel = item.selectedInflectionType
              ? (INFLECTION_LABELS[item.selectedInflectionType] ?? item.selectedInflectionType)
              : "原形";
            const selected = decisions[item.word] ?? {
              action: "register_as_is",
              lemma: null,
              spelling: null,
            };
            return (
              <div key={item.word} className="inflection-batch-row">
                <div>
                  <strong>{item.word}</strong>
                  <div className="muted">
                    {selected.lemma ? `lemma: ${selected.lemma}` : "lemma: (なし)"} / 種別:{" "}
                    {inflectionLabel}
                  </div>
                  {item.lemmaResolution === "resolved_from_inflection" && (
                    <div className="muted">候補は活用形から原形へ解決済み</div>
                  )}
                </div>
                <div className="inflection-batch-controls">
                  {(item.spellingCandidates ?? []).length > 0 && (
                    <select
                      className="inflection-batch-select"
                      value={selected.spelling ?? ""}
                      onChange={(e) => {
                        const spelling = e.target.value || null;
                        const nextCandidates = getLemmaCandidatesBySpelling(item, spelling);
                        setDecisions((prev) => ({
                          ...prev,
                          [item.word]: {
                            ...(prev[item.word] ?? {
                              action: item.suggestion,
                              lemma: null,
                              spelling: null,
                            }),
                            spelling,
                            lemma: nextCandidates[0]?.lemma ?? null,
                          },
                        }));
                      }}
                    >
                      <option value="">(綴り候補なし)</option>
                      {(item.spellingCandidates ?? []).map((candidate) => (
                        <option key={`${item.word}:spelling:${candidate.spelling}`} value={candidate.spelling}>
                          {candidate.spelling}
                          {candidate.source ? ` [${candidate.source}]` : ""}
                        </option>
                      ))}
                    </select>
                  )}
                  <select
                    className="inflection-batch-select"
                    value={selected.lemma ?? ""}
                    onChange={(e) =>
                      setDecisions((prev) => ({
                        ...prev,
                        [item.word]: {
                          ...(prev[item.word] ?? {
                            action: item.suggestion,
                            lemma: null,
                            spelling: null,
                          }),
                          lemma: e.target.value || null,
                        },
                      }))
                    }
                  >
                    <option value="">(lemmaなし)</option>
                    {getLemmaCandidatesBySpelling(item, selected.spelling ?? null).map((candidate) => (
                      <option key={`${item.word}:${candidate.lemma}`} value={candidate.lemma}>
                        {candidate.lemma}
                      </option>
                    ))}
                  </select>
                  <select
                    className="inflection-batch-select"
                    value={selected.action}
                    onChange={(e) =>
                      setDecisions((prev) => ({
                        ...prev,
                        [item.word]: {
                          ...(prev[item.word] ?? {
                            action: item.suggestion,
                            lemma: null,
                            spelling: null,
                          }),
                          action: e.target.value as InflectionAction,
                        },
                      }))
                    }
                  >
                    <option value="merge">原形に集約</option>
                    <option value="link">リンク付きで両方登録</option>
                    <option value="register_as_is">そのまま登録</option>
                  </select>
                  <button
                    type="button"
                    className="modal-cancel inflection-batch-reset-btn"
                    onClick={() =>
                      setDecisions((prev) => ({
                        ...prev,
                        [item.word]: initialDecisions[item.word] ?? {
                          action: item.suggestion,
                          lemma: item.selectedLemma ?? item.lemmaCandidates?.[0]?.lemma ?? null,
                          spelling: item.selectedSpelling ?? item.spellingCandidates?.[0]?.spelling ?? null,
                        },
                      }))
                    }
                  >
                    リセット
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="modal-cancel"
            onClick={() => setDecisions(initialDecisions)}
          >
            推奨に戻す
          </button>
          <button type="button" className="modal-cancel" onClick={onClose}>
            キャンセル
          </button>
          <button type="button" onClick={() => onConfirm(decisions)}>
            まとめて確定
          </button>
        </div>
      </div>
    </div>
  );
}
