import { useState } from "react";
import { Row } from "./atom";

interface WordFormProps {
  onSubmit: (word: string) => Promise<boolean | void> | boolean | void;
  disabled?: boolean;
  loading?: boolean;
}

export function WordForm({ onSubmit, disabled = false, loading = false }: WordFormProps) {
  const [value, setValue] = useState("");

  return (
    <Row
      as="form"
      className="word-form-row"
      onSubmit={async (e) => {
        e.preventDefault();
        const word = value.trim();
        if (!word) return;
        const result = await onSubmit(word);
        if (result !== false) {
          setValue("");
        }
      }}
    >
      <input
        className="word-form-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="単語を入力 (e.g. compute)"
        disabled={disabled}
      />
      <button className="word-form-submit" type="submit" disabled={disabled}>
        {loading ? "追加中..." : "追加"}
      </button>
    </Row>
  );
}
