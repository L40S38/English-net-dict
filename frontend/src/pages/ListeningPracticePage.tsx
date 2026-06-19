import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ListeningStepNav } from "../components/listening/ListeningStepNav";
import { PlaybackControls } from "../components/listening/PlaybackControls";
import { ScriptViewer } from "../components/listening/ScriptViewer";
import { VoiceCompareModal } from "../components/listening/VoiceCompareModal";
import { PageHeader } from "../components/PageHeader";
import { Card, Muted, Row } from "../components/atom";
import { useListeningSession } from "../lib/useListeningSession";
import type { ListeningStep, ListeningWordResult } from "../types";

const DICTATION_LEVEL_LABELS = ["全文表示", "穴埋め(少)", "穴埋め(多)", "白紙"];
const VALID_STEPS: ListeningStep[] = ["listen", "dictation", "read_aloud", "overlapping", "shadowing"];

export function ListeningPracticePage() {
  const params = useParams();
  const sessionId = Number(params.sessionId);
  const [compareLineId, setCompareLineId] = useState<number | null>(null);
  const [lineFeedback, setLineFeedback] = useState<Record<number, ListeningWordResult[]>>({});
  const [showTranslation, setShowTranslation] = useState(true);
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedInitialParams = useRef(false);

  const {
    session,
    sessionLoading,
    script,
    scriptLoading,
    setStep,
    setPlaybackSpeed,
    setDictationLevel,
    complete,
    recordAttempt,
    refetchScript,
  } = useListeningSession(sessionId);

  // URLの ?step=&level= を初回だけセッションに反映し、リロード/共有リンクで
  // 同じステップ・ディクテーションレベルに戻れるようにする。
  useEffect(() => {
    if (!session || appliedInitialParams.current) {
      return;
    }
    appliedInitialParams.current = true;
    const stepParam = searchParams.get("step");
    const levelParam = searchParams.get("level");
    if (stepParam && stepParam !== session.current_step && VALID_STEPS.includes(stepParam as ListeningStep)) {
      setStep(stepParam as ListeningStep);
    }
    const levelNum = levelParam !== null ? Number(levelParam) : NaN;
    if (Number.isFinite(levelNum) && levelNum !== session.dictation_level) {
      setDictationLevel(levelNum);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  // 以後はセッションの状態をURLに反映する(戻る/共有リンクで同じ位置に戻れるように)。
  useEffect(() => {
    if (!session) {
      return;
    }
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("step", session.current_step);
        next.set("level", String(session.dictation_level));
        return next;
      },
      { replace: true },
    );
  }, [session?.current_step, session?.dictation_level, setSearchParams]);

  if (!sessionId || Number.isNaN(sessionId)) {
    return (
      <main className="container">
        <Muted as="p">セッションIDが不正です。</Muted>
      </main>
    );
  }

  if (sessionLoading || scriptLoading || !session || !script) {
    return (
      <main className="container">
        <p>Loading…</p>
      </main>
    );
  }

  const handleSubmitLine = async (lineId: number, userText: string) => {
    const attempt = await recordAttempt({
      line_id: lineId,
      dictation_level: session.dictation_level,
      user_text: userText,
    });
    setLineFeedback((prev) => ({ ...prev, [lineId]: attempt.word_results }));
  };

  const isShadowing = session.current_step === "shadowing";
  const compareLine = script.lines.find((line) => line.id === compareLineId) ?? null;

  return (
    <main className="container">
      <PageHeader title={script.title} actions={<Link to="/listening">一覧へ戻る</Link>} />
      <ListeningStepNav currentStep={session.current_step} onChange={setStep} />

      {session.current_step === "dictation" && (
        <Card stack>
          <strong>ディクテーションレベル</strong>
          <Row>
            {DICTATION_LEVEL_LABELS.map((label, level) => (
              <button
                key={level}
                type="button"
                onClick={() => setDictationLevel(level)}
                disabled={session.dictation_level === level}
              >
                {label}
              </button>
            ))}
          </Row>
        </Card>
      )}

      <Row justify="between">
        <PlaybackControls speed={session.playback_speed} onChange={setPlaybackSpeed} />
        <label>
          <input
            type="checkbox"
            name="show-translation"
            checked={showTranslation}
            onChange={(e) => setShowTranslation(e.target.checked)}
          />
          {" "}和訳を表示
        </label>
      </Row>

      <ScriptViewer
        script={script}
        showText={!isShadowing}
        showTranslation={showTranslation}
        interactive={session.current_step === "dictation"}
        dictationLevel={session.dictation_level}
        playbackRate={session.playback_speed}
        lineFeedback={session.current_step === "dictation" ? lineFeedback : undefined}
        onSubmitLine={handleSubmitLine}
        onAudioGenerated={refetchScript}
        onSelectLine={(line) => setCompareLineId(line.id)}
      />

      {session.status !== "completed" && (
        <Row>
          <button type="button" onClick={() => complete()}>
            練習を完了する
          </button>
        </Row>
      )}

      <VoiceCompareModal
        line={compareLine}
        onClose={() => setCompareLineId(null)}
        onAudioGenerated={refetchScript}
      />
    </main>
  );
}
