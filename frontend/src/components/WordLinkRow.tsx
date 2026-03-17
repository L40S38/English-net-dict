import { Link } from "react-router-dom";

import { Muted } from "./atom";
import { hasMultipleWordTokens, tokenizeForWordLinks } from "../lib/tokenLinks";

interface Props {
  value: string;
  linkedWordId?: number | null;
  secondary?: string;
  status?: string;
}

export function WordLinkRow({ value, linkedWordId, secondary, status }: Props) {
  const showTokenLinks = hasMultipleWordTokens(value);
  const tokens = showTokenLinks ? tokenizeForWordLinks(value) : [];
  const hasSecondary = Boolean(secondary?.trim());
  const showSecondaryBelow = showTokenLinks && hasSecondary;

  return (
    <div className={`word-link-row${showSecondaryBelow ? " word-link-row-multiword" : ""}`}>
      <div className="word-link-main">
        {showTokenLinks ? (
          tokens.map((token) => (
            <Link key={`${value}-${token}`} to={`/words/${encodeURIComponent(token)}`}>
              {token}
            </Link>
          ))
        ) : (
          <Link to={linkedWordId ? `/words/${linkedWordId}` : `/words/${encodeURIComponent(value)}`}>{value}</Link>
        )}
      </div>
      {showSecondaryBelow ? (
        <>
          <Muted className="word-link-secondary">{secondary}</Muted>
          <Muted className="word-link-status">{status ?? ""}</Muted>
        </>
      ) : (
        <>
          <Muted>{secondary ?? ""}</Muted>
          <Muted>{status ?? ""}</Muted>
        </>
      )}
    </div>
  );
}
