import { useRef, useState } from "react";

import {
  InflectionBatchModal,
  type InflectionBatchDecision,
  type InflectionBatchItem,
} from "../components/InflectionBatchModal";
import { Muted } from "../components/atom";
import { migrationApi, wordApi } from "../lib/api";
import type {
  InflectionCheckResult,
  MigrationInflectionApplyDecision,
  MigrationInflectionApplyResponse,
  MigrationInflectionTarget,
} from "../types";

const CHECK_CHUNK_SIZE = 20;
const TARGET_PAGE_SIZE = 500;

type ModalState = {
  open: boolean;
  title: string;
  items: InflectionBatchItem[];
};

function collectLemmaCandidates(result: InflectionCheckResult) {
  const out: Array<{
    lemma: string;
    lemma_word_id?: number | null;
    inflection_type?: string | null;
  }> = [];
  for (const item of result.lemma_candidates ?? []) {
    out.push({
      lemma: item.lemma,
      lemma_word_id: item.lemma_word_id ?? null,
      inflection_type: item.inflection_type ?? null,
    });
  }
  for (const spelling of result.spelling_candidates ?? []) {
    for (const item of spelling.lemma_candidates ?? []) {
      out.push({
        lemma: item.lemma,
        lemma_word_id: item.lemma_word_id ?? null,
        inflection_type: item.inflection_type ?? null,
      });
    }
  }
  return out;
}

export function DevInflectionMigrationPage() {
  const [targets, setTargets] = useState<MigrationInflectionTarget[]>([]);
  const [checkResults, setCheckResults] = useState<InflectionCheckResult[]>([]);
  const [loadingTargets, setLoadingTargets] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [applyResult, setApplyResult] = useState<MigrationInflectionApplyResponse | null>(null);
  const [notice, setNotice] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [modalState, setModalState] = useState<ModalState>({
    open: false,
    title: "",
    items: [],
  });
  const resolverRef = useRef<((value: Record<string, InflectionBatchDecision> | null) => void) | null>(
    null,
  );

  const closeModal = (value: Record<string, InflectionBatchDecision> | null) => {
    resolverRef.current?.(value);
    resolverRef.current = null;
    setModalState({ open: false, title: "", items: [] });
  };

  const openModal = (params: { title: string; items: InflectionBatchItem[] }) =>
    new Promise<Record<string, InflectionBatchDecision> | null>((resolve) => {
      resolverRef.current = resolve;
      setModalState({ open: true, title: params.title, items: params.items });
    });

  const loadTargets = async () => {
    setLoadingTargets(true);
    setNotice("");
    setWarnings([]);
    try {
      let page = 1;
      let total = 0;
      const all: MigrationInflectionTarget[] = [];
      while (true) {
        const response = await migrationApi.listInflectionTargets({
          page,
          page_size: TARGET_PAGE_SIZE,
        });
        total = response.total;
        all.push(...response.words);
        if (all.length >= total || response.words.length === 0) {
          break;
        }
        page += 1;
      }
      setTargets(all);
      setCheckResults([]);
      setApplyResult(null);
      setNotice(`対象を ${all.length} 件読み込みました。`);
    } catch (error) {
      console.error(error);
      setNotice("対象単語の読み込みに失敗しました。");
    } finally {
      setLoadingTargets(false);
    }
  };

  const analyzeAndApply = async () => {
    if (targets.length === 0) {
      setNotice("先に対象単語を読み込んでください。");
      return;
    }
    setAnalyzing(true);
    setWarnings([]);
    setNotice("");
    setApplyResult(null);
    try {
      const collected: InflectionCheckResult[] = [];
      for (let start = 0; start < targets.length; start += CHECK_CHUNK_SIZE) {
        const chunk = targets.slice(start, start + CHECK_CHUNK_SIZE).map((item) => item.word);
        const response = await wordApi.checkInflection({ words: chunk });
        collected.push(...(response.results ?? []));
      }
      setCheckResults(collected);
      const inflectedItems = collected.filter((item) => item.is_inflected);
      if (inflectedItems.length === 0) {
        setNotice("活用形候補は見つかりませんでした。");
        return;
      }

      const decisions = await openModal({
        title: `活用形マイグレーション確認 (${inflectedItems.length}件)`,
        items: inflectedItems.map((item) => ({
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
      if (!decisions) {
        setNotice("適用をキャンセルしました。");
        return;
      }

      const targetByWord = new Map(targets.map((item) => [item.word.toLowerCase(), item]));
      const resultByWord = new Map(collected.map((item) => [item.word.toLowerCase(), item]));
      const applyPayload: MigrationInflectionApplyDecision[] = [];
      const unresolved: string[] = [];

      for (const [word, decision] of Object.entries(decisions)) {
        if (decision.action === "register_as_is") {
          continue;
        }
        const target = targetByWord.get(word.toLowerCase());
        const result = resultByWord.get(word.toLowerCase());
        if (!target || !result) {
          unresolved.push(`${word}: 対象データを解決できませんでした`);
          continue;
        }

        const desiredLemma = (decision.lemma ?? result.selected_lemma ?? "").trim().toLowerCase();
        if (!desiredLemma) {
          unresolved.push(`${word}: lemma が空です`);
          continue;
        }
        const chosen = collectLemmaCandidates(result).find(
          (item) =>
            item.lemma_word_id &&
            item.lemma.trim().toLowerCase() === desiredLemma,
        );
        if (!chosen?.lemma_word_id) {
          unresolved.push(`${word}: lemma_word_id が見つかりません（${decision.lemma ?? "-"})`);
          continue;
        }

        applyPayload.push({
          word_id: target.id,
          action: decision.action,
          lemma_word_id: chosen.lemma_word_id,
          inflection_type: chosen.inflection_type ?? result.selected_inflection_type ?? "inflection",
        });
      }

      setWarnings(unresolved);
      if (applyPayload.length === 0) {
        setNotice("適用可能な decision がありませんでした。");
        return;
      }

      const response = await migrationApi.applyInflection(applyPayload);
      setApplyResult(response);
      setNotice(`適用完了: applied=${response.applied}, skipped=${response.skipped}, errors=${response.errors}`);
    } catch (error) {
      console.error(error);
      setNotice("解析または適用に失敗しました。");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <main className="container stack">
      <h1>活用形マイグレーション（開発環境専用）</h1>
      <p>
        <Muted>
          既存DBの未リンク単語を対象に、`check-inflection` → レビュー → migration API 適用を実行します。
        </Muted>
      </p>
      <div className="row">
        <button type="button" onClick={loadTargets} disabled={loadingTargets || analyzing}>
          {loadingTargets ? "対象読み込み中..." : "対象を読み込む"}
        </button>
        <button type="button" onClick={analyzeAndApply} disabled={loadingTargets || analyzing || targets.length === 0}>
          {analyzing ? "解析・適用中..." : "解析して適用する"}
        </button>
      </div>

      <div className="card stack">
        <strong>対象件数: {targets.length}</strong>
        <Muted>解析結果件数: {checkResults.length}</Muted>
        {notice ? <div>{notice}</div> : null}
      </div>

      {warnings.length > 0 ? (
        <div className="card stack">
          <strong>スキップ理由（先頭20件）</strong>
          {warnings.slice(0, 20).map((warning) => (
            <div key={warning} className="muted">
              {warning}
            </div>
          ))}
          {warnings.length > 20 ? <div className="muted">...他 {warnings.length - 20} 件</div> : null}
        </div>
      ) : null}

      {applyResult ? (
        <div className="card stack">
          <strong>適用結果</strong>
          <div>applied: {applyResult.applied}</div>
          <div>skipped: {applyResult.skipped}</div>
          <div>errors: {applyResult.errors}</div>
        </div>
      ) : null}

      <InflectionBatchModal
        open={modalState.open}
        title={modalState.title}
        items={modalState.items}
        onClose={() => closeModal(null)}
        onConfirm={(value) => closeModal(value)}
      />
    </main>
  );
}
