import { useEffect, useMemo, useState } from "react";

import { Card, Muted, Row } from "./atom";
import { SHARED_API_BASE_URL_DEFAULT } from "../lib/sharedConfig";
import type { GroupImage, WordImage } from "../types";

interface ImageViewerProps {
  title: string;
  entityLabel: string;
  images: Array<WordImage | GroupImage>;
  defaultPromptRows?: number;
  fetchDefaultPrompt: () => Promise<string>;
  onGenerate: (prompt?: string) => Promise<unknown>;
  loading?: boolean;
}

export function ImageViewer({
  title,
  entityLabel,
  images,
  defaultPromptRows = 4,
  fetchDefaultPrompt,
  onGenerate,
  loading = false,
}: ImageViewerProps) {
  const [prompt, setPrompt] = useState("");
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const active = useMemo(() => images.find((image) => image.is_active), [images]);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? SHARED_API_BASE_URL_DEFAULT;
  const imageUrl = active
    ? `${baseUrl}/static/images/${active.file_path.split(/[\\/]/).pop()}`
    : null;

  useEffect(() => {
    let mounted = true;
    fetchDefaultPrompt()
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
  }, [fetchDefaultPrompt]);

  return (
    <Card stack>
      <h3>{title}</h3>
      {imageUrl ? (
        <div className="word-image-frame">
          <img src={imageUrl} alt={`${entityLabel} visual`} className="word-image" />
        </div>
      ) : (
        <Muted as="p">まだ画像は生成されていません。</Muted>
      )}
      <textarea
        rows={defaultPromptRows}
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
