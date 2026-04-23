import { Image, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, Muted, Row } from "./atom";
import { EMPTY_MESSAGES } from "../lib/constants";
import type { Word } from "../types";
import styles from "./WordCard.module.css";

const ICON_SIZE = 16;

interface WordCardProps {
  word: Word;
  deleting?: boolean;
  onDelete: (wordId: number) => void;
  /** false のとき削除ボタンを出さない（熟語の構成語など） */
  showDelete?: boolean;
  /** 熟語構成語のように images が空で API の image_count のみある場合 */
  imageCountOverride?: number;
}

export function WordCard({
  word,
  deleting = false,
  onDelete,
  showDelete = true,
  imageCountOverride,
}: WordCardProps) {
  const imageLen = imageCountOverride !== undefined ? imageCountOverride : (word.images?.length ?? 0);
  const hasImage = imageLen > 0;
  const chatCount = word.chat_session_count ?? 0;

  return (
    <Card hoverable stack className={styles.wordCard}>
      <Row justify="between">
        <Link to={`/words/${word.id}`}>
          <h3>{word.word}</h3>
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
          <small>{new Date(word.updated_at).toLocaleDateString()}</small>
        </div>
      </Row>
      <div className={styles.wordCardContent}>
        <Muted as="p">{word.phonetic || EMPTY_MESSAGES.noPhonetic}</Muted>
        <p>{word.definitions[0]?.meaning_ja ?? EMPTY_MESSAGES.noData}</p>
      </div>
      {showDelete ? (
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
      ) : null}
    </Card>
  );
}
