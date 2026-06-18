import { useRef, useState } from "react";

import { SHARED_API_BASE_URL_DEFAULT } from "../lib/sharedConfig";

interface AudioPlayButtonProps {
  audioPath?: string | null;
  onGenerate: () => Promise<{ audio_path?: string | null }>;
  label?: string;
}

export function AudioPlayButton({ audioPath, onGenerate, label = "🔊" }: AudioPlayButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT;
  const audioUrl = audioPath ? `${baseUrl}/static/${audioPath}` : null;

  const handleClick = async () => {
    if (audioUrl) {
      audioRef.current?.play();
      return;
    }
    setLoading(true);
    setError(false);
    try {
      const result = await onGenerate();
      const newPath = result.audio_path;
      if (newPath) {
        const url = `${baseUrl}/static/${newPath}`;
        const audio = new Audio(url);
        audioRef.current = audio;
        await audio.play();
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      title={audioUrl ? "再生" : "音声を生成"}
    >
      {loading ? "..." : error ? "⚠" : label}
    </button>
  );
}
