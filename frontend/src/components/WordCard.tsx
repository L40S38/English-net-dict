import { Image, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, Muted, Row } from "./atom";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Word } from "../types";

const ICON_SIZE = 16;

interface Props {
  word: Word;
  deleting?: boolean;
  onDelete: (wordId: number) => void;
}

export function WordCard({ word, deleting = false, onDelete }: Props) {
  const hasImage = (word.images?.length ?? 0) > 0;
  const chatCount = word.chat_session_count ?? 0;

  return (
    <Card hoverable stack className="word-card">
      <Row justify="between">
        <Link to={`/words/${word.id}`}>
          <h3>{word.word}</h3>
        </Link>
        <div className="word-card-meta">
          {hasImage && (
            <span title="画像あり" aria-label="画像あり">
              <Image size={ICON_SIZE} strokeWidth={2} />
            </span>
          )}
          {chatCount > 0 && (
            <span title={`チャット ${chatCount} 件`} aria-label={`チャット ${chatCount} 件`}>
              <MessageCircle size={ICON_SIZE} strokeWidth={2} />
              <small>{chatCount}</small>
            </span>
          )}
          <small>{new Date(word.updated_at).toLocaleDateString()}</small>
        </div>
      </Row>
      <div className="word-card-content">
        <Muted as="p">{word.phonetic || EMPTY_MESSAGES.noPhonetic}</Muted>
        <p>{word.definitions[0]?.meaning_ja ?? EMPTY_MESSAGES.noData}</p>
      </div>
      <button
        type="button"
        disabled={deleting}
        onClick={() => {
          const ok = window.confirm(`単語「${word.word}」を削除しますか？`);
          if (!ok) return;
          onDelete(word.id);
        }}
      >
        {deleting ? "削除中..." : "削除"}
      </button>
    </Card>
  );
}
