import { useMemo, useState } from "react";

import type { WordGroupItem } from "../types";

export type GroupCandidateSelectionKey = `w:${number}` | `p:${number}` | `e:${number}:${number}`;

export interface GroupCandidateAddedState {
  wordIds: Set<number>;
  phraseIds: Set<number>;
  exampleKeys: Set<string>;
}

export function createWordKey(wordId: number): GroupCandidateSelectionKey {
  return `w:${wordId}`;
}

export function createPhraseKey(phraseId: number): GroupCandidateSelectionKey {
  return `p:${phraseId}`;
}

export function createExampleKey(wordId: number, definitionId: number): GroupCandidateSelectionKey {
  return `e:${wordId}:${definitionId}`;
}

function isAddedKey(key: string, addedState: GroupCandidateAddedState): boolean {
  if (key.startsWith("w:")) {
    const [, rawWordId] = key.split(":");
    return addedState.wordIds.has(Number(rawWordId));
  }
  if (key.startsWith("p:")) {
    const [, rawPhraseId] = key.split(":");
    return addedState.phraseIds.has(Number(rawPhraseId));
  }
  if (key.startsWith("e:")) {
    return addedState.exampleKeys.has(key);
  }
  return false;
}

export function buildGroupCandidateAddedState(items: WordGroupItem[]): GroupCandidateAddedState {
  const wordIds = new Set<number>();
  const phraseIds = new Set<number>();
  const exampleKeys = new Set<string>();

  for (const item of items) {
    if (item.item_type === "word" && item.word_id != null) {
      wordIds.add(item.word_id);
      continue;
    }
    if (item.item_type === "phrase" && item.phrase_id != null) {
      phraseIds.add(item.phrase_id);
      continue;
    }
    if (item.item_type === "example" && item.word_id != null && item.definition_id != null) {
      exampleKeys.add(createExampleKey(item.word_id, item.definition_id));
    }
  }

  return { wordIds, phraseIds, exampleKeys };
}

export function useGroupCandidateSelection(addedState: GroupCandidateAddedState) {
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(() => new Set());

  const selectedCount = selectedKeys.size;

  const selectedList = useMemo(() => Array.from(selectedKeys), [selectedKeys]);

  const isSelected = (key: string) => selectedKeys.has(key);

  const toggle = (key: string) => {
    if (isAddedKey(key, addedState)) {
      return;
    }
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectAll = (keys: string[]) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      for (const key of keys) {
        if (isAddedKey(key, addedState)) {
          continue;
        }
        next.add(key);
      }
      return next;
    });
  };

  const clearAll = () => {
    setSelectedKeys(new Set());
  };

  const extractPayload = () => {
    const word_ids: number[] = [];
    const phrase_ids: number[] = [];
    const examples: Array<{ word_id: number; definition_id: number }> = [];

    for (const key of selectedKeys) {
      if (key.startsWith("w:")) {
        const [, rawWordId] = key.split(":");
        const wordId = Number(rawWordId);
        if (Number.isFinite(wordId) && wordId > 0) {
          word_ids.push(wordId);
        }
        continue;
      }
      if (key.startsWith("p:")) {
        const [, rawPhraseId] = key.split(":");
        const phraseId = Number(rawPhraseId);
        if (Number.isFinite(phraseId) && phraseId > 0) {
          phrase_ids.push(phraseId);
        }
        continue;
      }
      if (key.startsWith("e:")) {
        const [, rawWordId, rawDefinitionId] = key.split(":");
        const wordId = Number(rawWordId);
        const definitionId = Number(rawDefinitionId);
        if (
          Number.isFinite(wordId) &&
          wordId > 0 &&
          Number.isFinite(definitionId) &&
          definitionId > 0
        ) {
          examples.push({ word_id: wordId, definition_id: definitionId });
        }
      }
    }

    return {
      word_ids: Array.from(new Set(word_ids)),
      phrase_ids: Array.from(new Set(phrase_ids)),
      examples,
    };
  };

  return {
    selectedCount,
    selectedKeys: selectedList,
    isSelected,
    toggle,
    selectAll,
    clearAll,
    extractPayload,
  };
}
