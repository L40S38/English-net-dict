# Feature 03. 語源（Etymology）

前提：`backend/02_database.md`（クラスタ2: 語源）、`backend/03_api.md`（etymology_componentsセクション、wordsセクションの `/by-etymology-component`・`/enrich-etymology`）を読んでいること。

語源データは2つのレイヤーに分かれている。（1）各単語に1対1で紐づく `Etymology`＋そのサブテーブル（語源の分岐・バリエーション・言語チェーン・コンポーネント内訳）と、（2）単語に依存しない `etymology_components` キャッシュ（接頭辞・接尾辞・語根などのパーツ自体の情報）である。

## `etymology_components` キャッシュの役割

例えば `"tele-"` という接頭辞は `telephone`・`television`・`telegram` など多数の単語に共通して現れる。これを単語ごとに毎回スクレイプ・保持するのは無駄なので、コンポーネントのテキスト自体をキーにした独立したキャッシュテーブル `etymology_components` を持つ。各単語の `etymology_component_items.component_id` がこのキャッシュ行を参照する（`ON DELETE SET NULL`、任意参照）。

- 未登録のコンポーネントへのアクセス（`GET /api/etymology-components/{component_text}`が404）→ `POST /api/etymology-components/{component_text}` でWiktionaryの当該コンポーネントページ（`scrape_component_page()`）をスクレイプしてキャッシュを作成する（`etymology_component_service.py`）。
- `GET /api/words/by-etymology-component` は、あるコンポーネントを含む全単語を横断検索し、それらの関連語・派生語も集約して返す（`EtymologyComponentSearchResponse`）。

## 補完（enrichment）パスの発生タイミング

単語登録パイプライン（`features/01_word.md`）の中で語源が「汎用的すぎる」と判定された場合に自動で1回走るほか、単語詳細ページから `POST /api/words/{id}/enrich-etymology` を叩くことでいつでもオンデマンド再実行できる（`database_build etymology enrich-map` からも同じロジックを実行可能、`backend/05_cli.md` 参照）。このパスは `core_image`（語源の核となるイメージの説明文）と `branches`（意味の分岐）のみを更新し、`origin_word`/`raw_description` 等の他のフィールドやコンポーネント分解には触れない。

## フロントエンド固有の挙動

- **`EtymologySearchPage`**（`/etymology-search`）：語源コンポーネントの一覧・検索。
- **`EtymologyComponentPage`**（`/etymology-components/:componentText`）：コンポーネント詳細（Wiktionaryの意味・関連語・派生語）、そのコンポーネントを含む単語一覧、未登録時の登録導線、コンポーネントスコープのチャット。
- **`EtymologyMap.tsx`**：単語詳細ページ内の語源マップ可視化。コンポーネントを「単語としてリンクする」か「語源要素としてリンクする」かを、そのコンポーネントテキストが実在の単語かどうかで切り替えるロジックを持つ（`effectiveMode`）。

コンポーネントスコープのチャット（`ComponentChatPanel`）の仕組み自体は `features/06_chat.md` を参照。なお、語源コンポーネントチャットには他スコープと異なり `generate_chat_image` ツールが提供されない（同ファイル参照）。
