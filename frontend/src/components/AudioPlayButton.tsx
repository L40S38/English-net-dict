import { useRef, useState } from "react";

import { SHARED_API_BASE_URL_DEFAULT } from "../lib/sharedConfig";

interface AudioPlayButtonProps {
  audioPath?: string | null;
  onGenerate: () => Promise<{ audio_path?: string | null }>;
  label?: string;
  playbackRate?: number;
  /** 外部(例: スクリプト全体再生)が再生中であることを示すための強制ハイライト */
  forcePlaying?: boolean;
}

export function AudioPlayButton({
  audioPath,
  onGenerate,
  label = "🔊",
  playbackRate = 1,
  forcePlaying = false,
}: AudioPlayButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT;
  const audioUrl = audioPath ? `${baseUrl}/static/${audioPath}` : null;

  const bindPlaybackEvents = (audio: HTMLAudioElement) => {
    audio.onplay = () => setIsPlaying(true);
    audio.onpause = () => setIsPlaying(false);
    audio.onended = () => setIsPlaying(false);
  };

  const handleClick = async () => {
    if (audioUrl) {
      if (!audioRef.current) {
        audioRef.current = new Audio(audioUrl);
        bindPlaybackEvents(audioRef.current);
      }
      audioRef.current.playbackRate = playbackRate;
      void audioRef.current.play();
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
        audio.playbackRate = playbackRate;
        bindPlaybackEvents(audio);
        audioRef.current = audio;
        await audio.play();
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  const playing = isPlaying || forcePlaying;

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      title={audioUrl ? "再生" : "音声を生成"}
      className={`audio-play-button${playing ? " is-playing" : ""}`}
    >
      <span className="audio-play-icon">{loading ? "..." : error ? "⚠" : label}</span>
    </button>
  );
}
