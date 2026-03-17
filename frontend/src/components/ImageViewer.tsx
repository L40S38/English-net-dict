import { useEffect, useMemo, useState } from "react";

import { Card, Muted, Row } from "./atom";
import { wordApi } from "../lib/api";
import type { Word } from "../types";

interface Props {
  word: Word;
  onGenerate: (prompt?: string) => Promise<unknown>;
  loading?: boolean;
}

export function ImageViewer({ word, onGenerate, loading = false }: Props) {
  const [prompt, setPrompt] = useState("");
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const active = useMemo(() => word.images.find((x) => x.is_active), [word.images]);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const imageUrl = active
    ? `${baseUrl}/static/images/${active.file_path.split(/[\\/]/).pop()}`
    : null;

  useEffect(() => {
    let mounted = true;
    wordApi
      .getDefaultImagePrompt(word.id)
      .then((p) => {
        if (!mounted) return;
        setDefaultPrompt(p);
        setPrompt((prev) => prev || p);
      })
      .catch(() => {
        if (!mounted) return;
        setDefaultPrompt("");
      });
    return () => {
      mounted = false;
    };
  }, [word.id]);

  return (
    <Card stack>
      <h3>イメージ画像</h3>
      {imageUrl ? (
        <div className="word-image-frame">
          <img src={imageUrl} alt={`${word.word} visual`} className="word-image" />
        </div>
      ) : (
        <Muted as="p">まだ画像は生成されていません。</Muted>
      )}
      <textarea
        rows={4}
        value={prompt}
        placeholder="プロンプトを編集して再生成できます"
        onChange={(e) => setPrompt(e.target.value)}
        disabled={loading}
      />
      <Row>
        <button onClick={() => onGenerate(prompt || undefined)} disabled={loading}>
          {loading ? "生成中..." : imageUrl ? "再生成" : "画像を生成"}
        </button>
        <button
          type="button"
          onClick={() => setPrompt(defaultPrompt)}
          disabled={loading || !defaultPrompt}
        >
          デフォルトに戻す
        </button>
      </Row>
    </Card>
  );
}
