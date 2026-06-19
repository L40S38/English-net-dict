import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ListeningStepNav } from "../components/listening/ListeningStepNav";
import { PlaybackControls } from "../components/listening/PlaybackControls";
import { ScriptViewer } from "../components/listening/ScriptViewer";
import { VoiceCompareModal } from "../components/listening/VoiceCompareModal";
import { PageHeader } from "../components/PageHeader";
import { Card, Muted, Row } from "../components/atom";
import { useListeningSession } from "../lib/useListeningSession";
import type { ListeningWordResult } from "../types";

const DICTATION_LEVEL_LABELS = ["全文表示", "穴埋め(少)", "穴埋め(多)", "白紙"];

export function ListeningPracticePage() {
  const params = useParams();
  const sessionId = Number(params.sessionId);
  const [compareLineId, setCompareLineId] = useState<number | null>(null);
  const [lineFeedback, setLineFeedback] = useState<Record<number, ListeningWordResult[]>>({});
  const [showTranslation, setShowTranslation] = useState(true);

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
        <p>Loading...</p>
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
