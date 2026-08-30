# Backend 05. CLIとセットアップ

前提：`00_overview.md`、`01_architecture.md` を読んでいること。

## `database_build` CLI

`python -m database_build <domain> <action> [options]`（`backend/database_build/__main__.py` → `cli.py: main()`）で実行する統一運用CLI。ほぼ全サブコマンドが `--db`（DB上書き）を、多くが `--dry-run`/`--limit N`/`--word W` を共通オプションとして持つ。

| ドメイン | サブコマンド | 概要 |
|---|---|---|
| `word` | `refresh` | 既存単語を再スクレイプ＋GPT再構造化し、フィールド単位の差分を表示。`--dry-run`でコミットせずプレビューのみ |
| `word` | `rescrape` | 再スクレイプして差分表示なしで直接上書き（`refresh`より軽量） |
| `word` | `add --file` | テキストファイル（改行区切り）から新規単語を一括登録。活用形事前チェック付き |
| `etymology` | `refresh [--enrich-if-empty]` | 語源のみ再スクレイプ・再パース。空の場合は補完も実行可 |
| `etymology` | `enrich-map [--only-missing]` | `core_image`/`branches` のGPT補完のみ実行（HTTPの `/api/words/{id}/enrich-etymology` と同じロジック） |
| `etymology` | `normalize-json` | レガシーなJSON列形式の語源データを正規化テーブルへ一括移行（Alembic履歴を補完する一回限りの移行） |
| `etymology-components` | `create --component X` | 未登録の語源コンポーネントキャッシュを作成（HTTPの `POST /api/etymology-components/{text}` と同じロジック） |
| `etymology-components` | `rescrape --component X` | 既存コンポーネントの強制再スクレイプ |
| `phrases` | `enrich` | 単語の派生語・関連語のうち熟語らしきものの意味エンリッチを再実行 |
| `phrases` | `split` | スペースを含む旧`words`行を、正規の`Phrase`＋リンクされた構成`Word`に分割 |
| `inflection` | `import --input FILE` | CSVからlemma/活用形の対応関係を一括インポート |
| `inflection` | `report --output FILE [--apply-known-fixes]` | 活用形の疑いがある単語とlemma提案のCSVレポートを作成。既知の安全な修正は自動適用可 |
| `inspect` | `tables` | SQLite全テーブル名を表示 |
| `inspect` | `schema --table T` | 指定テーブルの `PRAGMA table_info` をJSON表示 |
| `search` | `--word KEYWORD [--limit N]` | `words.word` の部分一致検索（`id<TAB>word`形式で表示） |
| `preview` | `refresh` | `word refresh --dry-run` のエイリアス（差分のみのプレビュー） |
| `definitions` | `regenerate-examples` | 空/プレースホルダーの例文を再生成 |
| `forms` | `normalize-markers` | `words.forms` の比較級/最上級マーカーのノイズを正規化 |
| `forms` | `fix-noise` | ノイズの多い活用形データを検出し再取得 |

## 内部構成

`backend/database_build/ops/*.py`（`word.py`/`etymology.py`/`etymology_components.py`/`phrases.py`/`inflection.py`/`forms.py`/`definitions.py`/`common.py`）が実際の処理を実装し、`cli.py` はそれらの薄いディスパッチ層。`selectors.py`（対象レコードの絞り込み）・`runtime.py`（DBセッション初期化）・`reporting.py`（差分/レポート出力の整形）が横断的に使われる。

## HTTPエンドポイントとの意図的な重複

以下はCLIとHTTPエンドポイントの両方から同じサービス関数を呼び出す、意図された重複である（バグではない）。

| 機能 | CLI | HTTPエンドポイント |
|---|---|---|
| 語源のcore_image/branches補完 | `database_build etymology enrich-map` | `POST /api/words/{word_id}/enrich-etymology` |
| 単語の再スクレイプ | `database_build word rescrape` | `POST /api/words/{word_id}/rescrape` |
| 語源コンポーネント作成 | `database_build etymology-components create` | `POST /api/etymology-components/{component_text}` |

## レガシー `tmp_script/`

`backend/database_build/tmp_script/` 配下の旧 `patch_*.py`/`batch_*.py` は、`sys.argv` を新CLI形式（`database_build <domain> <action>`）に書き換えて `database_build.cli.main()` を呼び出すだけの薄い後方互換ラッパーである（例外は `benchmark_ingest.py` で、これは `add_words_from_file` の単体タイミング計測用スクリプト）。新規利用は非推奨、統一CLIを直接使うこと。

`backend/database_build/scripts/`（`search_db.py`/`inspect_db.py`/`preview_refresh.py`/`inflection_report.py`/`check_etymology.py`）も同じ `ops/*` 関数を直接呼ぶ独立実行可能なスクリプト群で、統一CLI以前の実装、または統一CLIと並行して単体実行したい場合の代替経路として残っている。

## セットアップ・起動スクリプト

ルート直下の `setup.sh`/`setup.ps1`/`setup.bat` は `backend/` で `uv sync`、`frontend/` で `npm ci && npm run build` を実行する。`start.sh`/`start.ps1`/`start.bat` はビルド済みの状態でバックエンド（uvicorn）とフロントエンド（`vite preview`）を起動する。ビルドの再実行は行わないため、依存関係やフロントエンド資産を変更した場合は `setup` を再実行する必要がある。実行モードの詳細（開発モード vs `start`モードのオリジン構成）は `01_architecture.md` を参照。
