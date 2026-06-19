import { useState } from "react";

import { Muted, Row, Stack } from "../atom";
import { listeningApi } from "../../lib/api";
import { SHARED_API_BASE_URL_DEFAULT } from "../../lib/sharedConfig";
import type { ListeningLine } from "../../types";

const ALL_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"];

interface VoiceComparePanelProps {
  line: ListeningLine;
  onAudioGenerated?: () => void;
}

export function VoiceComparePanel({ line, onAudioGenerated }: VoiceComparePanelProps) {
  const [generatingVoice, setGeneratingVoice] = useState<string | null>(null);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT;

  const usedVoices = new Set(line.audio_variants.map((v) => v.voice));
  const availableVoices = ALL_VOICES.filter((voice) => !usedVoices.has(voice));

  const handleGenerate = async (voice: string) => {
    setGeneratingVoice(voice);
    try {
      await listeningApi.generateLineAudio(line.id, voice);
      onAudioGenerated?.();
    } finally {
      setGeneratingVoice(null);
    }
  };

  return (
    <Stack>
      <Muted as="p">
        {line.speaker_label}: {line.text}
      </Muted>
      <Stack>
        {line.audio_variants.length === 0 && <Muted as="p">まだ音声が生成されていません。</Muted>}
        {line.audio_variants.map((variant) => (
          <Row key={variant.id} justify="between">
            <span>
              {variant.voice}
              {variant.is_primary ? "（既定）" : ""}
            </span>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <audio
              controls
              aria-label={`${variant.voice}の音声${variant.is_primary ? "(既定)" : ""}`}
              src={`${baseUrl}/static/${variant.audio_path}`}
            />
          </Row>
        ))}
      </Stack>
      {availableVoices.length > 0 && (
        <Row>
          {availableVoices.map((voice) => (
            <button
              key={voice}
              type="button"
              disabled={generatingVoice !== null}
              onClick={() => handleGenerate(voice)}
            >
              {generatingVoice === voice ? "生成中..." : `${voice}で生成`}
            </button>
          ))}
        </Row>
      )}
    </Stack>
  );
}
