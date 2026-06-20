import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PersonaIcon } from "./PersonaIcon";
import { Muted } from "../atom";
import { listeningApi } from "../../lib/api";
import { SHARED_API_BASE_URL_DEFAULT } from "../../lib/sharedConfig";
import type { ListeningPersona } from "../../types";

interface PersonaPickerProps {
  name: string;
  label: string;
  personas: ListeningPersona[];
  value: string | null;
  onChange: (voice: string | null) => void;
}

export function PersonaPicker({ name, label, personas, value, onChange }: PersonaPickerProps) {
  const [showDetail, setShowDetail] = useState(false);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT;
  const selected = personas.find((persona) => persona.voice === value) ?? null;

  const sampleQuery = useQuery({
    queryKey: ["listening-persona-sample", value],
    queryFn: () => listeningApi.getPersonaSample(value as string),
    enabled: showDetail && !!value,
    staleTime: Infinity,
  });

  return (
    <div className="persona-picker">
      <div className="persona-picker-row">
        <span className="persona-picker-field-label">{label}</span>
        <select
          name={name}
          value={value ?? ""}
          onChange={(e) => {
            onChange(e.target.value || null);
            setShowDetail(false);
          }}
        >
          <option value="">ランダム（おまかせ）</option>
          {personas.map((persona) => (
            <option key={persona.voice} value={persona.voice}>
              {persona.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!value}
          aria-expanded={showDetail}
          onClick={() => setShowDetail((prev) => !prev)}
        >
          詳細
        </button>
      </div>
      {showDetail && selected && (
        <div className="persona-picker-detail">
          <PersonaIcon voice={selected.voice} size={40} />
          <div className="persona-picker-detail-text">
            <strong>{selected.name}</strong>
            <p>{selected.description}</p>
            {sampleQuery.isLoading && <Muted>サンプル音声を生成中…</Muted>}
            {sampleQuery.isError && <Muted>サンプル音声を生成できませんでした。</Muted>}
            {sampleQuery.data && (
              // eslint-disable-next-line jsx-a11y/media-has-caption
              <audio
                controls
                aria-label={`${selected.name}の試聴音声`}
                src={`${baseUrl}/static/${sampleQuery.data.audio_path}`}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
