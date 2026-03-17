import { useEffect, useMemo, useState } from "react";

import { Card, Muted, Row } from "./atom";
import { groupApi } from "../lib/api";
import type { WordGroup } from "../types";

interface Props {
  group: WordGroup;
  onGenerate: (prompt?: string) => Promise<unknown>;
  loading?: boolean;
}

export function GroupImageViewer({ group, onGenerate, loading = false }: Props) {
  const [prompt, setPrompt] = useState("");
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const active = useMemo(() => group.images.find((x) => x.is_active), [group.images]);
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
  const imageUrl = active ? `${baseUrl}/static/images/${active.file_path.split(/[\\/]/).pop()}` : null;

  useEffect(() => {
    let mounted = true;
    groupApi
      .getDefaultImagePrompt(group.id)
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
  }, [group.id]);

  return (
    <Card stack>
      <h3>グループ画像</h3>
      {imageUrl ? (
        <div className="word-image-frame">
          <img src={imageUrl} alt={`${group.name} visual`} className="word-image" />
        </div>
      ) : (
        <Muted as="p">まだ画像は生成されていません。</Muted>
      )}
      <textarea
        rows={5}
        value={prompt}
        placeholder="プロンプトを編集して再生成できます"
        onChange={(e) => setPrompt(e.target.value)}
        disabled={loading}
      />
      <Row>
        <button onClick={() => onGenerate(prompt || undefined)} disabled={loading}>
          {loading ? "生成中..." : imageUrl ? "再生成" : "画像を生成"}
        </button>
        <button type="button" onClick={() => setPrompt(defaultPrompt)} disabled={loading || !defaultPrompt}>
          デフォルトに戻す
        </button>
      </Row>
    </Card>
  );
}

