import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { WeakWordsPanel } from "../components/listening/WeakWordsPanel";
import { Card, Field, Muted, RadioButtonGroup, Row, Stack } from "../components/atom";
import { listeningApi } from "../lib/api";
import { getErrorMessage } from "../lib/errors";
import type { ListeningScript } from "../types";

const LEVEL_OPTIONS = [
  { value: "beginner", label: "初級", description: "TOEIC 400点台 / 英検3級程度" },
  { value: "intermediate", label: "中級", description: "TOEIC 600点台 / 英検2級程度" },
  { value: "advanced", label: "上級", description: "TOEIC 800点以上 / 英検準1級以上" },
] as const;

const SPEAKER_COUNT_OPTIONS = [
  { value: "1", label: "1人" },
  { value: "2", label: "2人" },
  { value: "3", label: "3人" },
] as const;

export function ListeningHomePage() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [level, setLevel] = useState<string>("intermediate");
  const [speakerCount, setSpeakerCount] = useState<string>("1");
  const [isConversation, setIsConversation] = useState(false);
  const [customText, setCustomText] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["listening-sessions"],
    queryFn: () => listeningApi.listSessions(),
  });

  const startSession = async (script: ListeningScript) => {
    const session = await listeningApi.createSession(script.id);
    navigate(`/listening/sessions/${session.id}`);
  };

  const randomMutation = useMutation({
    mutationFn: () =>
      listeningApi.generateRandomScript({
        topic: topic.trim() || undefined,
        level,
        speaker_count: Number(speakerCount),
        is_conversation: isConversation,
      }),
    onSuccess: startSession,
    onError: (err) => setErrorMessage(getErrorMessage(err, "スクリプトの生成に失敗しました。")),
  });

  const customMutation = useMutation({
    mutationFn: () => listeningApi.createCustomScript(customText),
    onSuccess: startSession,
    onError: (err) => setErrorMessage(getErrorMessage(err, "スクリプトの変換に失敗しました。")),
  });

  const weakReviewMutation = useMutation({
    mutationFn: () => listeningApi.generateWeakReviewScript(),
    onSuccess: startSession,
    onError: (err) =>
      setErrorMessage(getErrorMessage(err, "弱点復習スクリプトの生成に失敗しました(苦手な単語の履歴が必要です)。")),
  });

  const busy = randomMutation.isPending || customMutation.isPending || weakReviewMutation.isPending;

  return (
    <main className="container">
      <PageHeader title="リスニング/シャドーイング練習" busy={busy} />
      {errorMessage && (
        <Muted as="p" role="status" aria-live="polite">
          {errorMessage}
        </Muted>
      )}
      <div className="detail-layout">
        <div className="detail-main">
          <Card stack>
            <h3>ランダム生成</h3>
            <Stack>
              <Field label="トピック(任意)">
                <input
                  name="topic"
                  autoComplete="off"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="例: travel"
                />
              </Field>
              <fieldset className="stack gap-sm">
                <legend>レベル</legend>
                <RadioButtonGroup
                  name="level"
                  options={LEVEL_OPTIONS}
                  value={level}
                  onChange={setLevel}
                />
              </fieldset>
              <fieldset className="stack gap-sm">
                <legend>話者数</legend>
                <RadioButtonGroup
                  name="speaker-count"
                  options={SPEAKER_COUNT_OPTIONS}
                  value={speakerCount}
                  onChange={setSpeakerCount}
                />
              </fieldset>
              <label>
                <input
                  type="checkbox"
                  name="is-conversation"
                  checked={isConversation}
                  onChange={(e) => setIsConversation(e.target.checked)}
                />
                {" "}会話形式にする
              </label>
              <Row>
                <button type="button" onClick={() => randomMutation.mutate()} disabled={busy}>
                  {randomMutation.isPending ? "生成中…" : "ランダム生成して開始"}
                </button>
              </Row>
            </Stack>
          </Card>

          <Card stack>
            <h3>カスタムスクリプト</h3>
            <Field label="カスタムスクリプト">
              <Muted as="p">英語のスクリプトを貼り付けると、リスニング問題に変換します。</Muted>
              <textarea
                name="custom-script"
                rows={6}
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                placeholder="ここに英語のスクリプトを入力…"
              />
            </Field>
            <Row>
              <button
                type="button"
                onClick={() => customMutation.mutate()}
                disabled={busy || !customText.trim()}
              >
                {customMutation.isPending ? "変換中…" : "このスクリプトで開始"}
              </button>
            </Row>
          </Card>

          <Card stack>
            <h3>弱点復習</h3>
            <Muted as="p">過去のディクテーションで間違えた単語を中心に新しいスクリプトを生成します。</Muted>
            <Row>
              <button type="button" onClick={() => weakReviewMutation.mutate()} disabled={busy}>
                {weakReviewMutation.isPending ? "生成中…" : "弱点復習を開始"}
              </button>
            </Row>
          </Card>

          <Card stack>
            <h3>過去のセッション</h3>
            {sessionsQuery.isLoading && <Muted as="p">読み込み中…</Muted>}
            {!sessionsQuery.isLoading && (sessionsQuery.data?.length ?? 0) === 0 && (
              <Muted as="p">まだセッションがありません。</Muted>
            )}
            <Stack>
              {sessionsQuery.data?.map((session) => (
                <Row key={session.id} justify="between">
                  <Link to={`/listening/sessions/${session.id}`}>
                    {session.script_title || `セッション#${session.id}`}
                  </Link>
                  <Muted>
                    {session.status === "completed" ? "完了" : "進行中"} ・{" "}
                    {new Date(session.updated_at).toLocaleString("ja-JP")}
                  </Muted>
                </Row>
              ))}
            </Stack>
          </Card>
        </div>
        <aside className="detail-side">
          <WeakWordsPanel />
        </aside>
      </div>
    </main>
  );
}
