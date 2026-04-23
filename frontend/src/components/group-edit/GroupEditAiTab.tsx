import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Tabs } from "../common/Tabs";
import {
  CandidateSection,
  ExampleCandidateRow,
  PhraseCandidateRow,
  WordCandidateCard,
} from "../group-candidates";
import { Card, Muted, Row } from "../atom";
import { groupApi } from "../../lib/api";
import {
  buildGroupCandidateAddedState,
  createExampleKey,
  createPhraseKey,
  createWordKey,
  useGroupCandidateSelection,
} from "../../lib/useGroupCandidateSelection";
import type { WordGroupItem } from "../../types";
import type { GroupCandidateSelectionPayload } from "./types";

const AI_PAGE_SIZE = 10;
type AiSubTabKey = "words" | "examples" | "phrases";

interface GroupEditAiTabProps {
  groupId: number;
  groupItems: WordGroupItem[];
  onAddSelection: (payload: GroupCandidateSelectionPayload) => Promise<void>;
  disableActions?: boolean;
}

function paginate<T>(items: T[], page: number, pageSize: number): T[] {
  const offset = (page - 1) * pageSize;
  return items.slice(offset, offset + pageSize);
}

export function GroupEditAiTab({
  groupId,
  groupItems,
  onAddSelection,
  disableActions = false,
}: GroupEditAiTabProps) {
  const [activeSubTab, setActiveSubTab] = useState<AiSubTabKey>("words");
  const [aiKeywords, setAiKeywords] = useState("");
  const [wordPage, setWordPage] = useState(1);
  const [examplePage, setExamplePage] = useState(1);
  const [phrasePage, setPhrasePage] = useState(1);

  const addedState = useMemo(() => buildGroupCandidateAddedState(groupItems), [groupItems]);
  const selection = useGroupCandidateSelection(addedState);

  const suggestMutation = useMutation({
    mutationFn: (keywords: string[]) => groupApi.suggest(groupId, { keywords, limit: 50 }),
    onSuccess: () => {
      setWordPage(1);
      setExamplePage(1);
      setPhrasePage(1);
      selection.clearAll();
    },
  });

  const candidates = suggestMutation.data?.candidates ?? [];
  const wordCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.item_type === "word"),
    [candidates],
  );
  const exampleCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.item_type === "example"),
    [candidates],
  );
  const phraseCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.item_type === "phrase"),
    [candidates],
  );

  const currentWordCandidates = paginate(wordCandidates, wordPage, AI_PAGE_SIZE);
  const currentExampleCandidates = paginate(exampleCandidates, examplePage, AI_PAGE_SIZE);
  const currentPhraseCandidates = paginate(phraseCandidates, phrasePage, AI_PAGE_SIZE);
  const subTabItems: Array<{ key: AiSubTabKey; label: string }> = [
    { key: "words", label: `単語 (${wordCandidates.length})` },
    { key: "examples", label: `例文 (${exampleCandidates.length})` },
    { key: "phrases", label: `熟語 (${phraseCandidates.length})` },
  ];

  const selectAllWords = () => {
    selection.selectAll(
      currentWordCandidates
        .map((candidate) => candidate.word_id)
        .filter((value): value is number => typeof value === "number")
        .map((wordId) => createWordKey(wordId)),
    );
  };

  const selectAllExamples = () => {
    const keys: string[] = [];
    for (const candidate of currentExampleCandidates) {
      if (candidate.word_id == null || candidate.definition_id == null) {
        continue;
      }
      keys.push(createExampleKey(candidate.word_id, candidate.definition_id));
    }
    selection.selectAll(keys);
  };

  const selectAllPhrases = () => {
    selection.selectAll(
      currentPhraseCandidates
        .map((candidate) => candidate.phrase_id)
        .filter((value): value is number => typeof value === "number")
        .map((phraseId) => createPhraseKey(phraseId)),
    );
  };

  const handleAddSelection = async () => {
    const payload = selection.extractPayload();
    if (
      payload.word_ids.length === 0 &&
      payload.phrase_ids.length === 0 &&
      payload.examples.length === 0
    ) {
      return;
    }
    await onAddSelection(payload);
    selection.clearAll();
  };

  return (
    <Card stack>
      <h3>AIで追加</h3>
      <label>
        <small>キーワード（カンマ区切り）</small>
        <input
          value={aiKeywords}
          onChange={(event) => setAiKeywords(event.target.value)}
          placeholder="例: food, cook, restaurant"
        />
      </label>
      <button
        type="button"
        onClick={() =>
          suggestMutation.mutate(
            aiKeywords
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
          )
        }
        disabled={suggestMutation.isPending || disableActions}
      >
        {suggestMutation.isPending ? "検索中..." : "AIで検索"}
      </button>

      <Tabs items={subTabItems} activeKey={activeSubTab} onChange={setActiveSubTab} />

      {activeSubTab === "words" ? (
        <CandidateSection
          title="単語候補"
          page={wordPage}
          total={wordCandidates.length}
          pageSize={AI_PAGE_SIZE}
          loading={suggestMutation.isPending}
          selectedCount={selection.selectedCount}
          onSelectAllPage={currentWordCandidates.length > 0 ? selectAllWords : undefined}
          onPrevPage={wordPage > 1 ? () => setWordPage((prev) => prev - 1) : undefined}
          onNextPage={
            wordCandidates.length > wordPage * AI_PAGE_SIZE
              ? () => setWordPage((prev) => prev + 1)
              : undefined
          }
        >
          {currentWordCandidates.map((candidate) => {
            if (candidate.word_id == null || !candidate.word) {
              return null;
            }
            const key = createWordKey(candidate.word_id);
            return (
              <WordCandidateCard
                key={`word-${candidate.word_id}-${candidate.score}`}
                word={{ id: candidate.word_id, word: candidate.word, definitions: [] }}
                checked={selection.isSelected(key)}
                disabled={addedState.wordIds.has(candidate.word_id) || disableActions}
                badge={
                  addedState.wordIds.has(candidate.word_id)
                    ? "追加済み"
                    : `score ${candidate.score.toFixed(1)}`
                }
                onToggle={() => selection.toggle(key)}
                showDefinitionRows={false}
              />
            );
          })}
        </CandidateSection>
      ) : null}

      {activeSubTab === "examples" ? (
        <CandidateSection
          title="例文候補"
          page={examplePage}
          total={exampleCandidates.length}
          pageSize={AI_PAGE_SIZE}
          loading={suggestMutation.isPending}
          selectedCount={selection.selectedCount}
          onSelectAllPage={currentExampleCandidates.length > 0 ? selectAllExamples : undefined}
          onPrevPage={examplePage > 1 ? () => setExamplePage((prev) => prev - 1) : undefined}
          onNextPage={
            exampleCandidates.length > examplePage * AI_PAGE_SIZE
              ? () => setExamplePage((prev) => prev + 1)
              : undefined
          }
        >
          {currentExampleCandidates.map((candidate, index) => {
            if (candidate.word_id == null || candidate.definition_id == null || !candidate.word) {
              return null;
            }
            const key = createExampleKey(candidate.word_id, candidate.definition_id);
            return (
              <ExampleCandidateRow
                key={`example-${candidate.word_id}-${candidate.definition_id}-${index}`}
                item={{
                  wordId: candidate.word_id,
                  definitionId: candidate.definition_id,
                  wordText: candidate.word,
                  partOfSpeech: candidate.definition_part_of_speech,
                  meaningJa: candidate.definition_meaning_ja,
                  exampleEn: candidate.example_en,
                  exampleJa: candidate.example_ja,
                }}
                checked={selection.isSelected(key)}
                disabled={addedState.exampleKeys.has(key) || disableActions}
                badge={
                  addedState.exampleKeys.has(key)
                    ? "追加済み"
                    : `score ${candidate.score.toFixed(1)}`
                }
                onToggle={() => selection.toggle(key)}
              />
            );
          })}
        </CandidateSection>
      ) : null}

      {activeSubTab === "phrases" ? (
        <CandidateSection
          title="熟語候補"
          page={phrasePage}
          total={phraseCandidates.length}
          pageSize={AI_PAGE_SIZE}
          loading={suggestMutation.isPending}
          selectedCount={selection.selectedCount}
          onSelectAllPage={currentPhraseCandidates.length > 0 ? selectAllPhrases : undefined}
          onPrevPage={phrasePage > 1 ? () => setPhrasePage((prev) => prev - 1) : undefined}
          onNextPage={
            phraseCandidates.length > phrasePage * AI_PAGE_SIZE
              ? () => setPhrasePage((prev) => prev + 1)
              : undefined
          }
        >
          {currentPhraseCandidates.map((candidate, index) => {
            if (candidate.phrase_id == null || !candidate.phrase_text) {
              return null;
            }
            const key = createPhraseKey(candidate.phrase_id);
            return (
              <PhraseCandidateRow
                key={`phrase-${candidate.phrase_id}-${index}`}
                phrase={{
                  id: candidate.phrase_id,
                  text: candidate.phrase_text,
                  meaning: candidate.phrase_meaning,
                }}
                checked={selection.isSelected(key)}
                disabled={addedState.phraseIds.has(candidate.phrase_id) || disableActions}
                badge={
                  addedState.phraseIds.has(candidate.phrase_id)
                    ? "追加済み"
                    : `score ${candidate.score.toFixed(1)}`
                }
                onToggle={() => selection.toggle(key)}
              />
            );
          })}
        </CandidateSection>
      ) : null}

      <Row>
        <Muted as="span">選択中 {selection.selectedCount} 件</Muted>
        <button
          type="button"
          className="modal-cancel"
          onClick={selection.clearAll}
          disabled={disableActions || selection.selectedCount === 0}
        >
          選択解除
        </button>
        <button
          type="button"
          onClick={() => void handleAddSelection()}
          disabled={disableActions || selection.selectedCount === 0}
        >
          選択項目を追加
        </button>
      </Row>
    </Card>
  );
}
