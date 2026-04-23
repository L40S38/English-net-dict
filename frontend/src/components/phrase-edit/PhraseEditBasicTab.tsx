import { Field } from "../atom";

interface PhraseEditBasicTabProps {
  text: string;
  meaning: string;
  setText: (value: string) => void;
  setMeaning: (value: string) => void;
  onEnrich: () => void;
  enriching: boolean;
}

export function PhraseEditBasicTab({
  text,
  meaning,
  setText,
  setMeaning,
  onEnrich,
  enriching,
}: PhraseEditBasicTabProps) {
  return (
    <div className="stack">
      <Field label="熟語">
        <input value={text} onChange={(event) => setText(event.target.value)} />
      </Field>
      <Field label="一言要約（プレビュー用）">
        <textarea rows={3} value={meaning} onChange={(event) => setMeaning(event.target.value)} />
      </Field>
      <button type="button" onClick={onEnrich} disabled={enriching}>
        {enriching ? "再取得中..." : "Wiktionaryから再取得"}
      </button>
    </div>
  );
}
