import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Muted, Row, Stack } from "../atom";
import { PersonaIcon } from "./PersonaIcon";
import { listeningApi } from "../../lib/api";
import { SHARED_API_BASE_URL_DEFAULT } from "../../lib/sharedConfig";
import type { ListeningLine } from "../../types";

interface VoiceComparePanelProps {
  line: ListeningLine;
  onAudioGenerated?: () => void;
}

export function VoiceComparePanel({ line, onAudioGenerated }: VoiceComparePanelProps) {
  const [generatingVoice, setGeneratingVoice] = useState<string | null>(null);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT;

  const personasQuery = useQuery({
    queryKey: ["listening-personas"],
    queryFn: () => listeningApi.getPersonas(),
    staleTime: Infinity,
  });
  const personas = personasQuery.data ?? [];
  const personaByVoice = new Map(personas.map((persona) => [persona.voice, persona]));

  const usedVoices = new Set(line.audio_variants.map((v) => v.voice));
  const availableVoices = personas.filter((persona) => !usedVoices.has(persona.voice));

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
        {line.audio_variants.map((variant) => {
          const persona = personaByVoice.get(variant.voice);
          const displayName = persona?.name ?? variant.voice;
          return (
            <Row key={variant.id} justify="between">
              <Row>
                <PersonaIcon voice={variant.voice} size={28} />
                <span>
                  {displayName}
                  {variant.is_primary ? "（既定）" : ""}
                </span>
              </Row>
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <audio
                controls
                aria-label={`${displayName}の音声${variant.is_primary ? "(既定)" : ""}`}
                src={`${baseUrl}/static/${variant.audio_path}`}
              />
            </Row>
          );
        })}
      </Stack>
      {availableVoices.length > 0 && (
        <Row>
          {availableVoices.map((persona) => (
            <button
              key={persona.voice}
              type="button"
              disabled={generatingVoice !== null}
              onClick={() => handleGenerate(persona.voice)}
              title={persona.description}
            >
              <Row>
                <PersonaIcon voice={persona.voice} size={20} />
                {generatingVoice === persona.voice ? "生成中..." : `${persona.name}で生成`}
              </Row>
            </button>
          ))}
        </Row>
      )}
    </Stack>
  );
}
