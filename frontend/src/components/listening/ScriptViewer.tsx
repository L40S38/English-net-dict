import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { AudioPlayButton } from "../AudioPlayButton";
import { Card, Muted, Row } from "../atom";
import { listeningApi } from "../../lib/api";
import { SHARED_API_BASE_URL_DEFAULT } from "../../lib/sharedConfig";
import type { ListeningLine, ListeningLineAudio, ListeningScript, ListeningWordResult } from "../../types";
import { selectBlankWordIndices } from "./dictationBlanks";

// レベル1=穴埋め(少) / レベル2=穴埋め(多) / レベル3=白紙(全て、別途処理)
const DICTATION_LEVEL_RATIOS: Record<number, number> = {
  1: 0.2,
  2: 0.45,
};

interface ScriptViewerProps {
  script: ListeningScript;
  showText?: boolean;
  showTranslation?: boolean;
  dictationLevel?: number;
  interactive?: boolean;
  playbackRate?: number;
  lineFeedback?: Record<number, ListeningWordResult[]>;
  onSubmitLine?: (lineId: number, userText: string) => void;
  onAudioGenerated?: () => void;
  onSelectLine?: (line: ListeningLine) => void;
}

interface LineToken {
  value: string;
  isWord: boolean;
  wordIndex: number | null;
  isBlank: boolean;
}

function tokenizeLine(text: string, dictationLevel: number, interactive: boolean): LineToken[] {
  const matches = Array.from(text.matchAll(/[A-Za-z']+|[^A-Za-z']+/g), (m) => m[0]);
  const words: string[] = [];
  for (const value of matches) {
    if (/[A-Za-z]/.test(value)) {
      words.push(value);
    }
  }

  let blankIndices: Set<number> = new Set();
  if (interactive && dictationLevel > 0) {
    if (dictationLevel >= 3) {
      blankIndices = new Set(words.map((_, i) => i));
    } else {
      blankIndices = selectBlankWordIndices(words, DICTATION_LEVEL_RATIOS[dictationLevel] ?? 0.2);
    }
  }

  let wordIndex = -1;
  return matches.map((value) => {
    const isWord = /[A-Za-z]/.test(value);
    if (!isWord) {
      return { value, isWord, wordIndex: null, isBlank: false };
    }
    wordIndex += 1;
    return { value, isWord, wordIndex, isBlank: blankIndices.has(wordIndex) };
  });
}

function LineRow({
  line,
  showText,
  showTranslation,
  dictationLevel,
  interactive,
  playbackRate,
  feedback,
  isActivePlayback,
  onSubmitLine,
  onAudioGenerated,
  onSelectLine,
}: {
  line: ListeningLine;
  showText: boolean;
  showTranslation: boolean;
  dictationLevel: number;
  interactive: boolean;
  playbackRate: number;
  feedback?: ListeningWordResult[];
  isActivePlayback: boolean;
  onSubmitLine?: (lineId: number, userText: string) => void;
  onAudioGenerated?: () => void;
  onSelectLine?: (line: ListeningLine) => void;
}) {
  const [inputs, setInputs] = useState<Record<number, string>>({});
  const tokens = useMemo(
    () => tokenizeLine(line.text, dictationLevel, interactive),
    [line.text, dictationLevel, interactive],
  );
  const primaryAudio = line.audio_variants.find((v) => v.is_primary) ?? line.audio_variants[0];
  const canSubmit = interactive && dictationLevel > 0 && !feedback;

  return (
    <div className={`listening-line${isActivePlayback ? " is-active-playback" : ""}`}>
      <div className="listening-line-main">
        <div className="listening-line-text">
          <strong>{line.speaker_label}</strong>
            <br />
          {showText &&
            tokens.map((token, idx) => {
              if (!token.isWord) {
                return <span key={idx}>{token.value}</span>;
              }
              const wordResult = feedback?.[token.wordIndex ?? -1];
              if (wordResult) {
                return (
                  <span
                    key={idx}
                    className={wordResult.is_correct ? "listening-word-correct" : "listening-word-incorrect"}
                  >
                    {token.value}
                  </span>
                );
              }
              if (token.isBlank) {
                return (
                  <input
                    key={idx}
                    className="listening-blank-input"
                    style={{ width: `${Math.max(token.value.length, 2) + 1}ch` }}
                    value={inputs[token.wordIndex!] ?? ""}
                    onChange={(e) =>
                      setInputs((prev) => ({ ...prev, [token.wordIndex!]: e.target.value }))
                    }
                  />
                );
              }
              return (
                <Link key={idx} to={`/words/${encodeURIComponent(token.value)}`}>
                  {token.value}
                </Link>
              );
            })}
        </div>
        <div className="listening-line-actions">
          <AudioPlayButton
            audioPath={primaryAudio?.audio_path}
            playbackRate={playbackRate}
            forcePlaying={isActivePlayback}
            onGenerate={async () => {
              const updated = await listeningApi.generateLineAudio(line.id);
              onAudioGenerated?.();
              const updatedPrimary = updated.audio_variants.find((v) => v.is_primary) ?? updated.audio_variants[0];
              return { audio_path: updatedPrimary?.audio_path ?? null };
            }}
          />
          {onSelectLine && (
            <button type="button" onClick={() => onSelectLine(line)}>
              聴き比べ
            </button>
          )}
        </div>
      </div>
      {showTranslation && line.translation_ja && (
        <Muted as="p" className="listening-line-translation">
          {line.translation_ja}
        </Muted>
      )}
      {canSubmit && (
        <Row>
          <button
            type="button"
            onClick={() => {
              const reconstructed = tokens
                .map((token) => {
                  if (!token.isWord) return token.value;
                  if (token.isBlank) return inputs[token.wordIndex!] ?? "";
                  return token.value;
                })
                .join("");
              onSubmitLine?.(line.id, reconstructed);
            }}
          >
            採点する
          </button>
        </Row>
      )}
    </div>
  );
}

const GENERATE_CONCURRENCY = 3;

interface GenerationProgress {
  done: number;
  total: number;
}

export function ScriptViewer({
  script,
  showText = true,
  showTranslation = true,
  dictationLevel = 0,
  interactive = false,
  playbackRate = 1,
  lineFeedback,
  onSubmitLine,
  onAudioGenerated,
  onSelectLine,
}: ScriptViewerProps) {
  const lines = useMemo(
    () => [...script.lines].sort((a, b) => a.sort_order - b.sort_order),
    [script.lines],
  );
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT;
  const playAllAudioRef = useRef<HTMLAudioElement | null>(null);
  const stopRequestedRef = useRef(false);
  const resolveCurrentRef = useRef<(() => void) | null>(null);
  const [isPlayingAll, setIsPlayingAll] = useState(false);
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);
  const [genProgress, setGenProgress] = useState<GenerationProgress | null>(null);
  const [activeLineId, setActiveLineId] = useState<number | null>(null);

  const playOne = (url: string, rate: number): Promise<void> =>
    new Promise((resolve) => {
      if (!playAllAudioRef.current) {
        playAllAudioRef.current = new Audio();
      }
      const audio = playAllAudioRef.current;
      resolveCurrentRef.current = resolve;
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.src = url;
      audio.playbackRate = rate;
      audio.play().catch(() => resolve());
    });

  // Generates audio for every line that doesn't have one yet (limited concurrency),
  // and returns a line-id -> playable-URL map covering ALL lines so playback never
  // has to wait on generation once this resolves.
  const generateAllAudio = async (): Promise<Map<number, string>> => {
    const urlByLineId = new Map<number, string>();
    const missing: ListeningLine[] = [];
    for (const line of lines) {
      const existing: ListeningLineAudio | undefined =
        line.audio_variants.find((v) => v.is_primary) ?? line.audio_variants[0];
      if (existing) {
        urlByLineId.set(line.id, `${baseUrl}/static/${existing.audio_path}`);
      } else {
        missing.push(line);
      }
    }
    if (missing.length === 0) {
      return urlByLineId;
    }

    let done = 0;
    setGenProgress({ done, total: missing.length });
    let nextIndex = 0;
    const worker = async () => {
      while (nextIndex < missing.length) {
        const line = missing[nextIndex];
        nextIndex += 1;
        try {
          const updated = await listeningApi.generateLineAudio(line.id);
          onAudioGenerated?.();
          const variant = updated.audio_variants.find((v) => v.is_primary) ?? updated.audio_variants[0];
          if (variant) {
            urlByLineId.set(line.id, `${baseUrl}/static/${variant.audio_path}`);
          }
        } catch {
          // skip lines that fail to generate; playback simply continues without them
        }
        done += 1;
        setGenProgress({ done, total: missing.length });
      }
    };
    await Promise.all(Array.from({ length: Math.min(GENERATE_CONCURRENCY, missing.length) }, worker));
    setGenProgress(null);
    return urlByLineId;
  };

  const handleGenerateAll = async () => {
    setIsGeneratingAll(true);
    try {
      await generateAllAudio();
    } finally {
      setIsGeneratingAll(false);
    }
  };

  const handlePlayAll = async () => {
    stopRequestedRef.current = false;
    setIsPlayingAll(true);
    try {
      const urlByLineId = await generateAllAudio();
      for (const line of lines) {
        if (stopRequestedRef.current) break;
        const url = urlByLineId.get(line.id);
        if (!url) continue;
        setActiveLineId(line.id);
        await playOne(url, playbackRate);
      }
    } finally {
      setActiveLineId(null);
      setIsPlayingAll(false);
    }
  };

  const handleStopAll = () => {
    stopRequestedRef.current = true;
    playAllAudioRef.current?.pause();
    resolveCurrentRef.current?.();
    setActiveLineId(null);
    setIsPlayingAll(false);
  };

  const progressLabel = genProgress ? `準備中... (${genProgress.done}/${genProgress.total})` : null;

  return (
    <Card stack>
      <Row justify="between">
        <strong>スクリプト</strong>
        <Row>
          <button
            type="button"
            onClick={() => void handleGenerateAll()}
            disabled={isGeneratingAll || isPlayingAll}
          >
            {isGeneratingAll ? (progressLabel ?? "生成中...") : "⬇ 全部生成"}
          </button>
          <button
            type="button"
            onClick={isPlayingAll ? handleStopAll : () => void handlePlayAll()}
            disabled={isGeneratingAll}
          >
            {isPlayingAll ? (progressLabel ?? "■ 停止") : "▶ 全部再生"}
          </button>
        </Row>
      </Row>
      <div>
        {lines.map((line) => (
          <LineRow
            key={line.id}
            line={line}
            showText={showText}
            showTranslation={showTranslation}
            dictationLevel={dictationLevel}
            interactive={interactive}
            playbackRate={playbackRate}
            feedback={lineFeedback?.[line.id]}
            isActivePlayback={activeLineId === line.id}
            onSubmitLine={onSubmitLine}
            onAudioGenerated={onAudioGenerated}
            onSelectLine={onSelectLine}
          />
        ))}
      </div>
    </Card>
  );
}
