import { Link } from "react-router-dom";

interface PhraseRegisterActionProps {
  text: string;
  phraseId: number | undefined;
  pending: boolean;
  disabled: boolean;
  onRegister: (text: string) => void;
}

/** 未登録熟語候補の「登録」ボタン、登録済みなら「詳細」リンクを出す共通トレーリング表示。 */
export function PhraseRegisterAction({
  text,
  phraseId,
  pending,
  disabled,
  onRegister,
}: PhraseRegisterActionProps) {
  if (phraseId) {
    return (
      <Link className="detail-link-button" to={`/phrases/${phraseId}`}>
        詳細
      </Link>
    );
  }
  return (
    <button
      type="button"
      className="detail-link-button"
      onClick={() => onRegister(text)}
      disabled={disabled}
    >
      {pending ? "登録中..." : "登録"}
    </button>
  );
}
