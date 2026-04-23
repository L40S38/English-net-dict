import { Link } from "react-router-dom";

import { Card, Muted, Row } from "../atom";

export interface CandidateExampleItem {
  wordId: number;
  wordText: string;
  definitionId: number;
  partOfSpeech?: string | null;
  meaningJa?: string | null;
  exampleEn?: string | null;
  exampleJa?: string | null;
}

interface ExampleCandidateRowProps {
  item: CandidateExampleItem;
  checked: boolean;
  disabled?: boolean;
  badge?: string;
  onToggle: () => void;
  trailing?: React.ReactNode;
}

export function ExampleCandidateRow({
  item,
  checked,
  disabled = false,
  badge,
  onToggle,
  trailing,
}: ExampleCandidateRowProps) {
  return (
    <Card variant="sub" stack>
      <Row justify="between">
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
          <Link to={`/words/${item.wordId}`}>{item.wordText}</Link>
          {item.partOfSpeech ? <strong>[{item.partOfSpeech}]</strong> : null}
          {item.meaningJa ? <span>{item.meaningJa}</span> : null}
          {badge ? <Muted as="span">[{badge}]</Muted> : null}
        </label>
        {trailing}
      </Row>
      {item.exampleEn ? <Muted as="p">{item.exampleEn}</Muted> : null}
      {item.exampleJa ? <Muted as="p">{item.exampleJa}</Muted> : null}
    </Card>
  );
}
