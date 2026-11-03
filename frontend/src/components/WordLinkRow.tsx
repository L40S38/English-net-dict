import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Muted } from "./atom";
import {
  getBracketedTokenFlags,
  hasMultipleWordTokens,
  isPlaceholderToken,
  tokenizeForWordLinks,
} from "../lib/tokenLinks";

interface WordLinkRowProps {
  value: string;
  linkedWordId?: number | null;
  secondary?: string;
  status?: string;
  trailing?: ReactNode;
  disableValueLink?: boolean;
}

export function WordLinkRow({
  value,
  linkedWordId,
  secondary,
  status,
  trailing,
  disableValueLink = false,
}: WordLinkRowProps) {
  const showTokenLinks = hasMultipleWordTokens(value);
  const tokens = showTokenLinks ? tokenizeForWordLinks(value) : [];
  const bracketFlags = showTokenLinks ? getBracketedTokenFlags(tokens) : [];
  const hasSecondary = Boolean(secondary?.trim());
  const showSecondaryBelow = hasSecondary;

  return (
    <div className={`word-link-row${showSecondaryBelow ? " word-link-row-stacked" : ""}`}>
      <div className="word-link-main">
        {showTokenLinks ? (
          tokens.map((token, idx) =>
            isPlaceholderToken(token) || bracketFlags[idx] ? (
              <span key={`${value}-${token}`}>{token}</span>
            ) : (
              <Link key={`${value}-${token}`} to={`/words/${encodeURIComponent(token)}`}>
                {token}
              </Link>
            ),
          )
        ) : (
          <>
            {disableValueLink ? (
              <span>{value}</span>
            ) : (
              <Link
                to={linkedWordId ? `/words/${linkedWordId}` : `/words/${encodeURIComponent(value)}`}
              >
                {value}
              </Link>
            )}
          </>
        )}
      </div>
      {showSecondaryBelow && (
        <Muted className="word-link-secondary">{secondary}</Muted>
      )}
      <Muted className="word-link-status">{trailing ?? status ?? ""}</Muted>
    </div>
  );
}
