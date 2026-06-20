const PALETTE = ["#f59e0b", "#3b82f6", "#10b981", "#ef4444", "#8b5cf6", "#ec4899"];

function colorForVoice(voice: string): string {
  let hash = 0;
  for (let i = 0; i < voice.length; i++) {
    hash = (hash * 31 + voice.charCodeAt(i)) % PALETTE.length;
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

interface PersonaIconProps {
  voice: string;
  size?: number;
}

export function PersonaIcon({ voice, size = 32 }: PersonaIconProps) {
  return (
    <span
      className="persona-icon"
      style={{ width: size, height: size, background: colorForVoice(voice) }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" width={size * 0.6} height={size * 0.6} fill="white">
        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
      </svg>
    </span>
  );
}
