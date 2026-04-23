export function tokenizeForWordLinks(text: string): string[] {
  return text
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

export function hasMultipleWordTokens(text: string): boolean {
  return tokenizeForWordLinks(text).length > 1;
}

const PLACEHOLDER_TOKENS = new Set(["A", "B", "C", "O", "S", "~"]);

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
