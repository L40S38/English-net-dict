export function tokenizeForWordLinks(text: string): string[] {
  return text
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

export function hasMultipleWordTokens(text: string): boolean {
  return tokenizeForWordLinks(text).length > 1;
}

const PLACEHOLDER_TOKENS = new Set(["A", "B", "C", "O", "S", "V", "~"]);

export function isPlaceholderToken(token: string): boolean {
  const value = token.trim();
  if (!value) return false;
  if (value === "~") return true;
  let normalized = value;
  if (normalized.endsWith("'s") || normalized.endsWith("’s")) {
    normalized = normalized.slice(0, -2);
  }
  return PLACEHOLDER_TOKENS.has(normalized);
}

// Tokens that fall inside a ( ) or [ ] span (which may cover multiple
// whitespace-separated tokens) should not be linked either.
export function getBracketedTokenFlags(tokens: string[]): boolean[] {
  const flags: boolean[] = [];
  let depth = 0;
  for (const token of tokens) {
    const opens = (token.match(/[([]/g) ?? []).length;
    const closes = (token.match(/[)\]]/g) ?? []).length;
    flags.push(depth > 0 || opens > 0);
    depth = Math.max(0, depth + opens - closes);
  }
  return flags;
}
