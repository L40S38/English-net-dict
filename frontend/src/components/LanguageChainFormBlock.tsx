import { Trash2 } from "lucide-react";
import { Card, Field } from "./atom";
import { ETYMOLOGY_RELATION_OPTIONS, LANGUAGE_OPTIONS } from "../lib/constants";
import type { LanguageChainLink } from "../types";

interface LanguageChainFormBlockProps {
  link: LanguageChainLink;
  index: number;
  onUpdate: (index: number, next: LanguageChainLink) => void;
  onRemove: (index: number) => void;
}

export function LanguageChainFormBlock({
  link,
  index,
  onUpdate,
  onRemove,
}: LanguageChainFormBlockProps) {
  const isKnownLanguage = LANGUAGE_OPTIONS.some((option) => option.code === link.lang);
  const languageSelectValue = !link.lang ? "" : isKnownLanguage ? link.lang : "__custom__";
  const isKnownRelation = ETYMOLOGY_RELATION_OPTIONS.some(
    (option) => option.value === link.relation,
  );
  const relationSelectValue = !link.relation ? "" : isKnownRelation ? link.relation : "__custom__";

  return (
    <Card variant="sub">
      <div className="inline-form-row">
        <Field label="言語" className="field-grow">
          <select
            value={languageSelectValue}
            onChange={(e) => {
              const next = e.target.value;
              if (next === "__custom__") {
                onUpdate(index, {
                  ...link,
                  lang: link.lang || "",
                  lang_name: link.lang_name || "",
                });
                return;
              }
              if (!next) {
                onUpdate(index, { ...link, lang: "", lang_name: undefined });
                return;
              }
              const selected = LANGUAGE_OPTIONS.find((option) => option.code === next);
              onUpdate(index, {
                ...link,
                lang: next,
                lang_name: selected?.name ?? next,
              });
            }}
          >
            <option value="">-- 言語を選択 --</option>
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.code} value={option.code}>
                {option.code} - {option.name}
              </option>
            ))}
            <option value="__custom__">その他（手動入力）</option>
          </select>
        </Field>
        {!isKnownLanguage && (
          <>
            <Field label="言語コード（手動）" className="field-grow">
              <input
                value={link.lang}
                onChange={(e) => onUpdate(index, { ...link, lang: e.target.value })}
                placeholder="例: la"
              />
            </Field>
            <Field label="言語名（手動）" className="field-grow">
              <input
                value={link.lang_name ?? ""}
                onChange={(e) =>
                  onUpdate(index, { ...link, lang_name: e.target.value || undefined })
                }
                placeholder="例: ラテン語"
              />
            </Field>
          </>
        )}
        <Field label="語形" className="field-grow">
          <input
            value={link.word}
            onChange={(e) => onUpdate(index, { ...link, word: e.target.value })}
            placeholder="例: explicare"
          />
        </Field>
        <Field label="関係" className="field-grow">
          <select
            value={relationSelectValue}
            onChange={(e) => {
              const next = e.target.value;
              if (next === "__custom__") {
                onUpdate(index, { ...link, relation: link.relation || "" });
                return;
              }
              onUpdate(index, { ...link, relation: next || undefined });
            }}
          >
            <option value="">-- 関係を選択 --</option>
            {ETYMOLOGY_RELATION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
            <option value="__custom__">その他（手動入力）</option>
          </select>
        </Field>
        {!isKnownRelation && (
          <Field label="関係（手動）" className="field-grow">
            <input
              value={link.relation ?? ""}
              onChange={(e) => onUpdate(index, { ...link, relation: e.target.value || undefined })}
              placeholder="例: cal"
            />
          </Field>
        )}
        <button
          type="button"
          className="icon-button-delete"
          onClick={() => onRemove(index)}
          aria-label="語源の来歴を削除"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </Card>
  );
}
