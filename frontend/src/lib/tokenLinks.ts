export function tokenizeForWordLinks(text: string): string[] {
  return text
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

export function hasMultipleWordTokens(text: string): boolean {
  return tokenizeForWordLinks(text).length > 1;
}
