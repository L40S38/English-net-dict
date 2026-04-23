import { Card, Muted, Row } from "./atom";
import type { Phrase } from "../types";

interface PhraseMeaningPanelProps {
  phrase: Phrase;
  onEnrich?: () => void;
  enriching?: boolean;
}

export function PhraseMeaningPanel({ phrase, onEnrich, enriching = false }: PhraseMeaningPanelProps) {
  return (
    <Card stack>
      <Row justify="between">
        <h3>熟語</h3>
        {onEnrich ? (
          <button type="button" onClick={onEnrich} disabled={enriching}>
            {enriching ? "再取得中..." : "Wiktionaryから再取得"}
          </button>
        ) : null}
      </Row>
      <p>{phrase.text}</p>
      <Muted as="p">{phrase.meaning || "意味は未設定です。"}</Muted>
    </Card>
  );
}
