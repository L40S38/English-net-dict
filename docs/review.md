
プロジェクトの主要部分を確認した結果を、3つの観点でまとめます。

---

# プロジェクト実装レビュー

## 1. 今後の拡張性（コンポーネント共通化・アトミックデザイン）

### 良い点

- **Atom の整理**: `frontend/src/components/atom/` に Card, Stack, Row, Field, Chip, ChipList, Muted, LoadingBanner があり、責務が分かれています。`Card` の `as={Link}` や `Row` の `as="form"` のように、多態的な API で再利用しやすい設計です。
- **チャットの責務分離**: 表示用の `ChatPanel`（props で状態を受け取る）と、データ取得・mutations を持つ `WordChatPanel` / `ComponentChatPanel` が分かれており、同じ UI を単語用・語源要素用で使い回せています。
- **WordLinkRow の再利用**: 派生語（`DerivationsPanel`）と関連語（`RelatedWords`）の両方で `WordLinkRow` が使われ、リンク＋補足表示のパターンが共通化されています。
- **型・定数**: `types/index.ts` でドメイン型を一括定義、`lib/constants.ts` でラベルや空メッセージを集約しており、変更時の影響範囲を把握しやすいです。

### 改善を検討したい点

- **Molecules / Organisms の不足**: アトミックデザインの「Molecules」「Organisms」に相当する層がなく、機能コンポーネント（WordCard, DerivationsPanel など）が atom の直上に並んでいます。  
  例: 「意味・例文」1件分のブロックを `DefinitionCard`、「分岐」1行を `BranchRow` のような molecule に切り出すと、編集画面や一覧の追加時に再利用しやすくなります。
- **WordEditPage の肥大化**: 約 450 行で、定義・派生語・関連語のフォームが同じような「Field + input/select + 追加/削除」の繰り返しになっています。  
  `DefinitionFormBlock` / `DerivationFormBlock` / `RelatedWordFormBlock` のようなサブコンポーネントに分けると、見通しとテストがしやすくなります。
  -> 対応したい
- **WordCard の分岐**: `showDeleteButton` で 2 つの return に分かれており、構造が重複しています。共通部分を 1 つの JSX にまとめ、削除ボタンの有無だけ props で切り替える形にすると、修正時の二重管理を避けられます。
  -> 削除ボタンありに統一したい
- **検索 UI**: HomePage の検索が `div` + `input` の直書きです。`Field` や将来的な `SearchInput` のような共通コンポーネントにすると、他ページで検索を足すときの拡張が楽になります。
　-> 対応したい

---

## 2. 初見での読みやすさ・コメント

### 良い点

- **型と Props**: 各コンポーネントの `Props` や、`types/index.ts` の型定義で「何を渡すか」が明確です。
- **ファイル・ディレクトリ名**: `WordCard`, `DerivationsPanel`, `ChatPanel` など、役割が名前から推測しやすいです。

### 改善を検討したい点

- **コメントがほぼない**: フロント・バックエンドとも、ファイル先頭の説明や「なぜこうしているか」のコメントがほとんどありません。  
  特に次のような箇所は、短文のコメントがあると読み手に優しいです。
  - **バックエンド**: `words.py` の `_is_forced_morpheme_component`, `_resolve_component_link`, `_to_word_read` の語源コンポーネント enrichment など、ドメインルールが込められた関数。
  -> もう少しリファクタしてから対応するか決める
  - **フロント**: `WordEditPage` の `parseJsonArray`、`ChatPanel` の `normalizeText`（文字化け検出）、`EtymologyMap` の `effectiveMode` / 語源要素リンクの分岐。
  -> もう少しリファクタしてから対応するか決める
- **複雑なロジック**: `EtymologyMap` の「単語リンク vs 語源要素リンク」の切り替え、`WordDetailPage` の `wordKey`（ID vs 文字列）の扱いなどは、数行の説明があると意図が伝わりやすくなります。
-> 対応したい
- **モジュール役割の説明**: `backend/app` や `frontend/src` の役割（routers / services / models の関係など）を README や 1 ファイル目に短く書いておくと、初見の人が迷いにくくなります。
-> 対応不要

---

## 3. データベース / バックエンド / フロントエンドの役割分担

### 良い点

- **バックエンドの層分離**:
  - **Routers**: HTTP とパラメータ検証に集中。`chat.py` は薄く、`words.py` もエンドポイント単位では「DB 取得 → サービス呼び出し → スキーマで返す」という流れが分かります。
  - **Services**: `chat_service`, `gpt_service`, `etymology_component_service`, スクレイパーなど、ビジネスロジックがサービスにまとまっています。
  - **Models / Schemas**: SQLAlchemy の `models.py` と Pydantic の `schemas.py` が分かれており、API 契約と永続化が分離されています。
- **フロントエンド**:
  - データ取得は `lib/api.ts` に集約され、`wordApi` / `chatApi` / `componentChatApi` / `componentApi` で整理されています。
  - ページコンポーネントは API と型を利用するだけで、HTTP の詳細は隠れています。
- **DB アクセス**: フロントは API 経由のみで、DB に直接触れない構成になっています。

### 改善を検討したい点

- **words ルーターの責務**: `words.py` に `_apply_structured_payload`, `_to_word_read`（コンポーネントの linked_word_id 解決など）, `_link_derivations`, `_link_related_words` など、ドメイン寄りの処理が多く入っています。  
  これらを `word_service` や `WordRepository` のようなモジュールに移すと、「HTTP 層」と「単語ドメインの扱い」の境界がはっきりし、テストや将来の API 増設がしやすくなります。
  -> 対応したい
- **Repository 層の有無**: 現状はサービスやルーターが直接 `Session` と `models` を使っています。規模が大きくなった場合は、Repository を挟んで「永続化の方法」を隠すと、DB 変更やキャッシュ導入時の影響範囲を限定しやすくなります。
　-> 対応したいがRepositoryというクラス名だと分かりにくいので別の名前にしてほしい
- **マイグレーション**: `main.py` の `_ensure_runtime_migrations()` に SQLite 用のスキーマ変更が直書きされています。  
  マイグレーション専用モジュール（例: `app/migrations/` や `alembic`）に切り出すと、起動処理がすっきりし、本番のスキーマ管理も扱いやすくなります。
  -> 対応したい
- **API モジュール分割**: `api.ts` は 1 ファイルで 200 行弱です。現状でも `wordApi` などで分離されているので無理は不要ですが、さらに機能が増える場合は `api/words.ts`, `api/chat.ts` のようにエンドポイント単位でファイルを分ける選択肢があります。
-> 現時点では対応不要だが、今後1000行超になる見込みになったら分割するかもしれない

---

## まとめ

| 観点 | 評価 | 要約 |
|------|------|------|
| **拡張性** | 良いが伸ばせる | atom と ChatPanel の共通化はよくできている。編集ページの分割と、molecule レベルのコンポーネント化でさらに拡張しやすくなる。 |
| **可読性・コメント** | 改善の余地あり | 型と名前で意図はある程度伝わるが、複雑なロジックとドメインルールにコメントが少ない。重要箇所に短文コメントと、プロジェクト/モジュールの説明があるとよい。 |
| **役割分担** | おおむね適切 | フロント/API/DB の境界は明確。バックエンドは「words のドメイン処理をサービス/リポジトリに寄せる」「マイグレーションの切り出し」でさらに整理できる。 |

全体として、小〜中規模の個人用アプリとして構造はしっかりしており、上記を少しずつ取り入れると、機能追加や他人が読むときの負荷をさらに下げられると思います。