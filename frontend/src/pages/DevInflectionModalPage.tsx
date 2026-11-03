/**
 * 開発環境専用: 活用形一括確認モーダルのデザイン確認用ページ
 * /dev/inflection-modal でアクセス
 */
import { useState } from "react";

import { Muted } from "../components/atom";
import { InflectionBatchModal } from "../components/InflectionBatchModal";
import { DEV_INFLECTION_SAMPLE_ITEMS } from "./devInflectionSampleData";

export function DevInflectionModalPage() {
  const [open, setOpen] = useState(true);

  return (
    <main className="container">
      <h1>活用形チェックモーダル（デザイン確認）</h1>
      <p>
        <Muted>
          開発環境専用。本番ビルドではこのパスは表示されません。`batch_inflection_report.csv`
          の内容をフロント側定数にコピーしたサンプルを表示しています。
        </Muted>
      </p>
      <button type="button" onClick={() => setOpen(true)}>
        モーダルを開く
      </button>
      <div className="card stack">
        <strong>現在の確認対象（{DEV_INFLECTION_SAMPLE_ITEMS.length}件）</strong>
        {DEV_INFLECTION_SAMPLE_ITEMS.map((item) => (
          <div key={item.word} className="muted">
            {item.word} / suggestion: {item.suggestion}
          </div>
        ))}
      </div>

      <InflectionBatchModal
        open={open}
        title="活用形の一括確認（デモ）"
        items={DEV_INFLECTION_SAMPLE_ITEMS}
        onClose={() => setOpen(false)}
        onConfirm={(actions) => {
          alert(`確定 actions:\n${JSON.stringify(actions, null, 2)}`);
          setOpen(false);
        }}
      />
    </main>
  );
}
