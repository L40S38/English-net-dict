import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { Tabs } from "../common/Tabs";
import { CandidateSection, PhraseCandidateRow, WordCandidateCard } from "../group-candidates";
import { Card, Muted, Row } from "../atom";
import { wordApi } from "../../lib/api";
import {
  buildGroupCandidateAddedState,
  createExampleKey,
  createPhraseKey,
  createWordKey,
  useGroupCandidateSelection,
} from "../../lib/useGroupCandidateSelection";
import type { WordGroupItem } from "../../types";
import type { GroupCandidateSelectionPayload } from "./types";

const MANUAL_PAGE_SIZE = 20;
type ManualSubTabKey = "words" | "phrases";

interface GroupEditManualTabProps {
  groupItems: WordGroupItem[];
  onAddSelection: (payload: GroupCandidateSelectionPayload) => Promise<void>;
  disableActions?: boolean;
}

export function GroupEditManualTab({
  groupItems,
  onAddSelection,
  disableActions = false,
}: GroupEditManualTabProps) {
  const [activeSubTab, setActiveSubTab] = useState<ManualSubTabKey>("words");
  const [wordKeywordInput, setWordKeywordInput] = useState("");
  const [wordKeyword, setWordKeyword] = useState("");
  const [wordPage, setWordPage] = useState(1);
  const [phrasePage, setPhrasePage] = useState(1);

  const addedState = useMemo(() => buildGroupCandidateAddedState(groupItems), [groupItems]);
  const selection = useGroupCandidateSelection(addedState);

  const searchMutation = useMutation({
    mutationFn: (params: { q: string; pageWords: number; pagePhrases: number }) =>
      wordApi.searchForGroup({
        q: params.q,
        page_words: params.pageWords,
        page_phrases: params.pagePhrases,
        page_size: MANUAL_PAGE_SIZE,
      }),
  });

  const result = searchMutation.data;
  const words = result?.items ?? [];
  const phrases = result?.phrases ?? [];

  useEffect(() => {
    selection.clearAll();
  }, [wordKeyword]);

  const runSearch = (options?: { wordPage?: number; phrasePage?: number }) => {
    const keyword = wordKeyword.trim();
    if (!keyword) {
      return;
    }
    const nextWordPage = options?.wordPage ?? wordPage;
    const nextPhrasePage = options?.phrasePage ?? phrasePage;
    searchMutation.mutate({ q: keyword, pageWords: nextWordPage, pagePhrases: nextPhrasePage });
  };

  const selectAllWordPage = () => {
    const keys: string[] = [];
    for (const word of words) {
      keys.push(createWordKey(word.id));
      for (const definition of word.definitions ?? []) {
        keys.push(createExampleKey(word.id, definition.id));
      }
    }
    selection.selectAll(keys);
  };

  const selectAllPhrasePage = () => {
    selection.selectAll(phrases.map((phrase) => createPhraseKey(phrase.id)));
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

  const hasKeyword = wordKeyword.trim().length > 0;
  const subTabItems: Array<{ key: ManualSubTabKey; label: string }> = [
    { key: "words", label: `単語 (${result?.total ?? 0})` },
    { key: "phrases", label: `熟語 (${result?.phrases_total ?? 0})` },
  ];

  return (
    <Card stack>
      <h3>手動追加</h3>
      <label>
        <small>単語/熟語を検索</small>
        <Row>
          <input
            value={wordKeywordInput}
            onChange={(event) => setWordKeywordInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              const next = wordKeywordInput.trim();
              setWordKeyword(next);
              setWordPage(1);
              setPhrasePage(1);
              if (next) {
                searchMutation.mutate({ q: next, pageWords: 1, pagePhrases: 1 });
              }
            }}
            placeholder="単語/熟語を検索（Enterまたは検索ボタン）"
            style={{ flex: 1 }}
          />
          <button
            type="button"
            onClick={() => {
              const next = wordKeywordInput.trim();
              setWordKeyword(next);
              setWordPage(1);
              setPhrasePage(1);
              if (next) {
                searchMutation.mutate({ q: next, pageWords: 1, pagePhrases: 1 });
              }
            }}
            disabled={searchMutation.isPending || wordKeywordInput.trim().length === 0 || disableActions}
          >
            {searchMutation.isPending ? "検索中..." : "検索"}
          </button>
          {hasKeyword ? (
            <button
              type="button"
              onClick={() => {
                setWordKeywordInput("");
                setWordKeyword("");
                setWordPage(1);
                setPhrasePage(1);
                selection.clearAll();
                searchMutation.reset();
              }}
            >
              クリア
            </button>
          ) : null}
        </Row>
      </label>

      <Tabs items={subTabItems} activeKey={activeSubTab} onChange={setActiveSubTab} />

      {activeSubTab === "words" ? (
        <CandidateSection
          title="単語検索結果"
          page={wordPage}
          total={result?.total ?? 0}
          pageSize={MANUAL_PAGE_SIZE}
          loading={searchMutation.isPending}
          selectedCount={selection.selectedCount}
          onSelectAllPage={words.length > 0 ? selectAllWordPage : undefined}
          onPrevPage={
            wordPage > 1
              ? () => {
                  const next = wordPage - 1;
                  setWordPage(next);
                  runSearch({ wordPage: next });
                }
              : undefined
          }
          onNextPage={
            (result?.total ?? 0) > wordPage * MANUAL_PAGE_SIZE
              ? () => {
                  const next = wordPage + 1;
                  setWordPage(next);
                  runSearch({ wordPage: next });
                }
              : undefined
          }
          emptyMessage={hasKeyword ? "単語候補はありません。" : "検索してください。"}
        >
          {words.map((word) => (
            <WordCandidateCard
              key={word.id}
              word={word}
              checked={selection.isSelected(createWordKey(word.id))}
              disabled={addedState.wordIds.has(word.id) || disableActions}
              badge={addedState.wordIds.has(word.id) ? "追加済み" : undefined}
              onToggle={() => selection.toggle(createWordKey(word.id))}
              isDefinitionChecked={(definitionId) =>
                selection.isSelected(createExampleKey(word.id, definitionId))
              }
              isDefinitionDisabled={(definitionId) =>
                addedState.exampleKeys.has(createExampleKey(word.id, definitionId)) || disableActions
              }
              definitionBadge={(definitionId) =>
                addedState.exampleKeys.has(createExampleKey(word.id, definitionId)) ? "追加済み" : null
              }
              onToggleDefinition={(definition) => selection.toggle(createExampleKey(word.id, definition.id))}
            />
          ))}
        </CandidateSection>
      ) : null}

      {activeSubTab === "phrases" ? (
        <CandidateSection
          title="熟語検索結果"
          page={phrasePage}
          total={result?.phrases_total ?? 0}
          pageSize={MANUAL_PAGE_SIZE}
          loading={searchMutation.isPending}
          selectedCount={selection.selectedCount}
          onSelectAllPage={phrases.length > 0 ? selectAllPhrasePage : undefined}
          onPrevPage={
            phrasePage > 1
              ? () => {
                  const next = phrasePage - 1;
                  setPhrasePage(next);
                  runSearch({ phrasePage: next });
                }
              : undefined
          }
          onNextPage={
            (result?.phrases_total ?? 0) > phrasePage * MANUAL_PAGE_SIZE
              ? () => {
                  const next = phrasePage + 1;
                  setPhrasePage(next);
                  runSearch({ phrasePage: next });
                }
              : undefined
          }
          emptyMessage={hasKeyword ? "熟語候補はありません。" : "検索してください。"}
        >
          {phrases.map((phrase) => (
            <PhraseCandidateRow
              key={phrase.id}
              phrase={phrase}
              checked={selection.isSelected(createPhraseKey(phrase.id))}
              disabled={addedState.phraseIds.has(phrase.id) || disableActions}
              badge={addedState.phraseIds.has(phrase.id) ? "追加済み" : undefined}
              onToggle={() => selection.toggle(createPhraseKey(phrase.id))}
            />
          ))}
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
