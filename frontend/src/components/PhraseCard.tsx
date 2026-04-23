import { Image, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, Muted, Row } from "./atom";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Phrase } from "../types";
import styles from "./WordCard.module.css";

const ICON_SIZE = 16;

interface PhraseCardProps {
  phrase: Phrase;
  deleting?: boolean;
  onDelete: (phraseId: number) => void;
}

export function PhraseCard({ phrase, deleting = false, onDelete }: PhraseCardProps) {
  const hasImage = (phrase.images?.length ?? 0) > 0;
  const chatCount = phrase.chat_session_count ?? 0;

  return (
    <Card hoverable stack className={styles.wordCard}>
      <Row justify="between">
        <Link to={`/phrases/${phrase.id}`}>
          <h3>{phrase.text}</h3>
        </Link>
        <div className={styles.wordCardMeta}>
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
          <small>{new Date(phrase.updated_at).toLocaleDateString()}</small>
        </div>
      </Row>
      <div className={styles.wordCardContent}>
        <Muted as="p">{phrase.meaning || EMPTY_MESSAGES.noData}</Muted>
      </div>
      <button
        type="button"
        disabled={deleting}
        onClick={() => {
          const ok = window.confirm(`熟語「${phrase.text}」を削除しますか？`);
          if (!ok) return;
          onDelete(phrase.id);
        }}
      >
        {deleting ? "削除中..." : "削除"}
      </button>
    </Card>
  );
}
