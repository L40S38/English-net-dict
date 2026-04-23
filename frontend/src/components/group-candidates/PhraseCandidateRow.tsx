import { Link } from "react-router-dom";

import { Card, Muted, Row } from "../atom";

export interface CandidatePhraseItem {
  id: number;
  text: string;
  meaning?: string | null;
}

interface PhraseCandidateRowProps {
  phrase: CandidatePhraseItem;
  checked: boolean;
  disabled?: boolean;
  badge?: string;
  onToggle: () => void;
  trailing?: React.ReactNode;
}

export function PhraseCandidateRow({
  phrase,
  checked,
  disabled = false,
  badge,
  onToggle,
  trailing,
}: PhraseCandidateRowProps) {
  return (
    <Card variant="sub" stack>
      <Row justify="between">
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
          <strong>{phrase.text}</strong>
          {phrase.meaning ? <Muted as="span">- {phrase.meaning}</Muted> : null}
          {badge ? <Muted as="span">[{badge}]</Muted> : null}
        </label>
        <Row>
          <Link className="detail-link-button" to={`/phrases/${phrase.id}`}>
            詳細
          </Link>
          {trailing}
        </Row>
      </Row>
    </Card>
  );
}
