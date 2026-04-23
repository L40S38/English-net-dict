import { Link } from "react-router-dom";

import { Card, Muted, Row, Stack } from "../atom";

export interface CandidateDefinitionItem {
  id: number;
  part_of_speech?: string | null;
  meaning_ja?: string | null;
  meaning_en?: string | null;
  example_en?: string | null;
  example_ja?: string | null;
}

export interface CandidateWordItem {
  id: number;
  word: string;
  phonetic?: string | null;
  definitions?: CandidateDefinitionItem[];
}

interface WordCandidateCardProps {
  word: CandidateWordItem;
  checked: boolean;
  disabled?: boolean;
  badge?: string;
  onToggle: () => void;
  showDefinitionRows?: boolean;
  isDefinitionChecked?: (definitionId: number) => boolean;
  isDefinitionDisabled?: (definitionId: number) => boolean;
  definitionBadge?: (definitionId: number) => string | null;
  onToggleDefinition?: (definition: CandidateDefinitionItem) => void;
  trailing?: React.ReactNode;
}

export function WordCandidateCard({
  word,
  checked,
  disabled = false,
  badge,
  onToggle,
  showDefinitionRows = true,
  isDefinitionChecked,
  isDefinitionDisabled,
  definitionBadge,
  onToggleDefinition,
  trailing,
}: WordCandidateCardProps) {
  const definitions = showDefinitionRows ? word.definitions ?? [] : [];

  return (
    <Card variant="sub" stack>
      <Row justify="between">
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
          <Link to={`/words/${word.id}`}>{word.word}</Link>
          {word.phonetic ? <Muted as="span">{word.phonetic}</Muted> : null}
          {badge ? <Muted as="span">[{badge}]</Muted> : null}
        </label>
        {trailing}
      </Row>

      {definitions.length > 0 ? (
        <Stack>
          {definitions.map((definition) => {
            const definitionChecked = isDefinitionChecked?.(definition.id) ?? false;
            const definitionDisabled = isDefinitionDisabled?.(definition.id) ?? false;
            const definitionTag = definitionBadge?.(definition.id);
            return (
              <Card key={definition.id} variant="sub" stack>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                  <input
                    type="checkbox"
                    checked={definitionChecked}
                    disabled={definitionDisabled || !onToggleDefinition}
                    onChange={() => onToggleDefinition?.(definition)}
                  />
                  {definition.part_of_speech ? <strong>[{definition.part_of_speech}]</strong> : null}
                  {definition.meaning_ja ? <span>{definition.meaning_ja}</span> : <Muted as="span">意味なし</Muted>}
                  {definitionTag ? <Muted as="span">[{definitionTag}]</Muted> : null}
                </label>
                {definition.meaning_en ? <Muted as="p">{definition.meaning_en}</Muted> : null}
                {definition.example_en ? <Muted as="p">{definition.example_en}</Muted> : null}
                {definition.example_ja ? <Muted as="p">{definition.example_ja}</Muted> : null}
              </Card>
            );
          })}
        </Stack>
      ) : null}
    </Card>
  );
}
