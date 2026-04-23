import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Tabs } from "../components/common/Tabs";
import { Row } from "../components/atom";
import { phraseApi } from "../lib/api";
import { PhraseEditBasicTab } from "../components/phrase-edit/PhraseEditBasicTab";
import { PhraseEditDefinitionsTab } from "../components/phrase-edit/PhraseEditDefinitionsTab";
import { PhraseEditWordsTab } from "../components/phrase-edit/PhraseEditWordsTab";
import type { PhraseDefinition, WordSummary } from "../types";

type EditTabKey = "basic" | "definitions" | "words";

const EDIT_TABS: Array<{ key: EditTabKey; label: string }> = [
  { key: "basic", label: "基本情報" },
  { key: "definitions", label: "定義" },
  { key: "words", label: "構成語" },
];

export function PhraseEditPage() {
  const params = useParams();
  const phraseId = Number(params.phraseId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const phraseQuery = useQuery({
    queryKey: ["phrase", phraseId],
    queryFn: () => phraseApi.get(phraseId),
    enabled: Number.isFinite(phraseId) && phraseId > 0,
  });

  const [text, setText] = useState("");
  const [meaning, setMeaning] = useState("");
  const [definitions, setDefinitions] = useState<PhraseDefinition[]>([]);
  const [words, setWords] = useState<WordSummary[]>([]);
  const [activeTab, setActiveTab] = useState<EditTabKey>("basic");

  useEffect(() => {
    if (!phraseQuery.data) return;
    setText(phraseQuery.data.text);
    setMeaning(phraseQuery.data.meaning ?? "");
    setDefinitions(phraseQuery.data.definitions ?? []);
    setWords(phraseQuery.data.words ?? []);
  }, [phraseQuery.data]);

  const payload = useMemo(
    () => ({
      text: text.trim(),
      meaning: meaning.trim(),
      definitions: definitions.map((item, idx) => ({
        id: item.id > 0 ? item.id : null,
        part_of_speech: item.part_of_speech,
        meaning_en: item.meaning_en,
        meaning_ja: item.meaning_ja,
        example_en: item.example_en,
        example_ja: item.example_ja,
        sort_order: idx,
      })),
      word_ids: words.map((word) => word.id),
    }),
    [text, meaning, definitions, words],
  );

  const saveMutation = useMutation({
    mutationFn: () => phraseApi.updateFull(phraseId, payload),
    onSuccess: async (updated) => {
      await queryClient.invalidateQueries({ queryKey: ["phrase", phraseId] });
      await queryClient.invalidateQueries({ queryKey: ["phrases"] });
      navigate(`/phrases/${updated.id}`);
    },
  });

  const enrichMutation = useMutation({
    mutationFn: () => phraseApi.enrich(phraseId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["phrase", phraseId] });
    },
  });

  if (!phraseQuery.data) {
    return (
      <main className="container">
        <p>Loading...</p>
      </main>
    );
  }

  return (
    <main className="container">
      <Row justify="between">
        <h2>{phraseQuery.data.text} の編集</h2>
        <Row>
          <Link to={`/phrases/${phraseQuery.data.id}`}>詳細へ戻る</Link>
        </Row>
      </Row>

      <Tabs items={EDIT_TABS} activeKey={activeTab} onChange={setActiveTab} />

      {activeTab === "basic" && (
        <PhraseEditBasicTab
          text={text}
          meaning={meaning}
          setText={setText}
          setMeaning={setMeaning}
          onEnrich={() => enrichMutation.mutate()}
          enriching={enrichMutation.isPending}
        />
      )}
      {activeTab === "definitions" && (
        <PhraseEditDefinitionsTab definitions={definitions} setDefinitions={setDefinitions} />
      )}
      {activeTab === "words" && <PhraseEditWordsTab words={words} setWords={setWords} />}

      <Row>
        <button type="button" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? "保存中..." : "保存"}
        </button>
        <Link to={`/phrases/${phraseQuery.data.id}`}>キャンセル</Link>
      </Row>
    </main>
  );
}
