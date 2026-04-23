import type {
  InflectionBatchDecision,
  InflectionBatchItem,
} from "../components/InflectionBatchModal";
import type { Word } from "../types";

import { wordApi } from "./api";

export function resolveBulkChunkSize(): number {
  const raw = Number(import.meta.env.VITE_BULK_CHUNK_SIZE ?? "5");
  if (!Number.isFinite(raw)) {
    return 5;
  }
  return Math.min(100, Math.max(1, Math.trunc(raw)));
}

export type OpenInflectionModalFn = (params: {
  title: string;
  items: InflectionBatchItem[];
}) => Promise<Record<string, InflectionBatchDecision> | null>;

/**
 * HomePage 一括登録と同じ手順: チャンクごとに check-inflection → 必要ならモーダル → 単語ごと POST /api/words。
 */
export async function createWordsWithInflectionCheck(
  words: string[],
  openInflectionModal: OpenInflectionModalFn,
  options?: {
    onChunkProgress?: (completed: number, total: number) => void;
  },
): Promise<Word[]> {
  const BULK_CHUNK_SIZE = resolveBulkChunkSize();
  const total = words.length;
  const onProgress = options?.onChunkProgress;
  onProgress?.(0, total);

  const allCreatedWords: Word[] = [];

  for (let start = 0; start < words.length; start += BULK_CHUNK_SIZE) {
    const chunk = words.slice(start, start + BULK_CHUNK_SIZE);
    const inflectionCheck = await wordApi.checkInflection({ words: chunk });
    const checkResults = inflectionCheck.results ?? [];
    const inflected = checkResults.filter((item) => item.is_inflected);
    let inflectionDecisions: Record<string, InflectionBatchDecision> = {};
    if (inflected.length > 0) {
      const selectedActions = await openInflectionModal({
        title: `活用形チェック (${start + 1}-${Math.min(start + chunk.length, words.length)}件目)`,
        items: inflected.map((item) => ({
          word: item.word,
          selectedLemma: item.selected_lemma ?? null,
          selectedSpelling: item.selected_spelling ?? null,
          lemmaResolution: item.lemma_resolution ?? null,
          selectedInflectionType: item.selected_inflection_type ?? null,
          lemmaCandidates: (item.lemma_candidates ?? []).map((candidate) => ({
            lemma: candidate.lemma,
            lemmaWordId: candidate.lemma_word_id ?? null,
            inflectionType: candidate.inflection_type ?? null,
          })),
          spellingCandidates: (item.spelling_candidates ?? []).map((entry) => ({
            spelling: entry.spelling,
            source: entry.source ?? null,
            selectedLemma: entry.selected_lemma ?? null,
            lemmaResolution: entry.lemma_resolution ?? null,
            lemmaCandidates: (entry.lemma_candidates ?? []).map((candidate) => ({
              lemma: candidate.lemma,
              lemmaWordId: candidate.lemma_word_id ?? null,
              inflectionType: candidate.inflection_type ?? null,
            })),
          })),
          suggestion: item.suggestion ?? "register_as_is",
        })),
      });
      if (!selectedActions) {
        onProgress?.(Math.min(start + chunk.length, words.length), total);
        continue;
      }
      inflectionDecisions = selectedActions;
    }
    for (const word of chunk) {
      const matched = checkResults.find((item) => item.word.toLowerCase() === word.toLowerCase());
      if (matched?.is_inflected) {
        const decision = inflectionDecisions[word];
        const action = decision?.action ?? matched.suggestion ?? "register_as_is";
        const lemmaWord = decision?.lemma ?? matched.selected_lemma ?? null;
        const createdWords = await wordApi.create(word, {
          inflection_action: action,
          lemma_word: action === "register_as_is" ? null : lemmaWord,
        });
        allCreatedWords.push(...createdWords);
      } else {
        const createdWords = await wordApi.create(word);
        allCreatedWords.push(...createdWords);
      }
    }
    onProgress?.(Math.min(start + chunk.length, words.length), total);
  }

  return allCreatedWords;
}
