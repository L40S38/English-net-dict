import type { Word } from "../types";

import { wordApi } from "./api";

/**
 * 熟語登録は活用形判定を行わず、バックエンドの ingest ロジックに委ねる。
 */
export async function createPhrasesBulk(
  phrases: string[],
  options?: {
    onChunkProgress?: (completed: number, total: number) => void;
    onItemError?: (phrase: string, error: unknown) => void;
  },
): Promise<Word[]> {
  const total = phrases.length;
  const onProgress = options?.onChunkProgress;
  const onItemError = options?.onItemError;
  onProgress?.(0, total);
  const allCreatedWords: Word[] = [];

  for (let i = 0; i < phrases.length; i += 1) {
    const phrase = phrases[i];
    try {
      const response = await wordApi.create(phrase);
      allCreatedWords.push(...response.words);
    } catch (error) {
      onItemError?.(phrase, error);
    }
    onProgress?.(i + 1, total);
  }

  return allCreatedWords;
}
