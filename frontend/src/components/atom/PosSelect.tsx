import { POS_OPTIONS } from "../../lib/constants";

interface PosSelectProps {
  value: string;
  onChange: (value: string) => void;
}

export function PosSelect({ value, onChange }: PosSelectProps) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      {!POS_OPTIONS.some((option) => option.value === value) && (
        <option value={value}>{value}</option>
      )}
      {POS_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
