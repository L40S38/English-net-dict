import { Row } from "../atom";

interface PlaybackControlsProps {
  speed: number;
  onChange: (speed: number) => void;
}

const PRESETS = [2.0, 1.5, 1.0];

export function PlaybackControls({ speed, onChange }: PlaybackControlsProps) {
  return (
    <Row>
      {PRESETS.map((preset) => (
        <button key={preset} type="button" onClick={() => onChange(preset)} disabled={speed === preset}>
          {preset.toFixed(1)}x
        </button>
      ))}
      <label>
        速度:
        <input
          type="number"
          name="playback-speed"
          autoComplete="off"
          min={0.25}
          max={3}
          step={0.05}
          value={speed}
          onChange={(e) => {
            const value = Number(e.target.value);
            if (Number.isFinite(value) && value > 0) {
              onChange(value);
            }
          }}
        />
      </label>
    </Row>
  );
}
