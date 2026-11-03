# Backend 03. APIリファレンス

前提：`00_overview.md`、`01_architecture.md`、`02_database.md` を読んでいること。全10ルーター・92エンドポイントを網羅する。個々のロジックの詳しい説明はここには書かず、各表の末尾から `features/` の該当ファイルへリンクする。

## マウントポイント索引

| ルーターファイル | URLプレフィックス | 対応機能 |
|---|---|---|
| `words.py` | `/api/words` | `features/01_word.md` |
| `etymology_components.py` | `/api/etymology-components` | `features/03_etymology.md` |
| `images.py` | `/api` | `features/07_image_generation.md` |
| `audio.py` | `/api` | `features/01_word.md`, `features/02_phrase.md`, `features/05_listening.md` |
| `chat.py` | `/api` | `features/06_chat.md` |
| `listening.py` | `/api/listening` | `features/05_listening.md` |
| `groups.py` | `/api/groups` | `features/04_group.md` |
| `phrases.py` | `/api` | `features/02_phrase.md` |
| `search.py` | `/api/search` | — |
| `migration.py` | `/api/migration` | `features/08_inflection_lemma_merge.md` |

その他：`GET /health`（死活監視）。フロントエンドは開発時は別オリジンから、`start` モードでは同一FastAPIプロセスから配信される（`01_architecture.md`）。

---

## words（`/api/words`）— 24エンドポイント

単語のCRUDと、スクレイピング＋GPTによる自動登録を担う、最大のルーター。

| Method | Path | 概要 | Request要点 | Response要点 |
|---|---|---|---|---|
| GET | `` | 単語一覧（検索・ページング・ソート） | クエリ：検索語、ソート順（`last_viewed_at`/`created_at`/`updated_at`/`word`） | `WordListResponse` |
| GET | `/search-for-group` | グループ作成UI向けの多段階検索（熟語優先→AND→OR） | クエリ：キーワード | `GroupSearchResponse`（単語＋熟語） |
| GET | `/suggest` | オートコンプリート候補 | クエリ：prefix | `list[str]` |
| GET | `/by-text/{word_text}` | 単語テキストで取得（大小文字非依存）、`last_viewed_at` 更新 | — | `WordRead` |
| GET | `/by-etymology-component` | 指定した語源コンポーネントを含む単語群＋集約された関連語・派生語 | クエリ：component text | `EtymologyComponentSearchResponse` |
| GET | `/{word_id}` | IDで取得、`last_viewed_at` 更新 | — | `WordRead` |
| POST | `` | **単語（または熟語）の新規登録**。スクレイピング＋GPT構造化を実行 | `WordCreateRequest`、クエリ：`inflection_action`/`llm_mode`/`phrase_enrich_mode`/`example_mode`/`phrase_parallelism` | `WordCreateResponse` |
| POST | `/bulk` | 複数単語の一括登録（1件ごとに個別トランザクション） | `BulkWordRequest` | `list[WordRead]` |
| POST | `/by-ids` | ID配列で一括取得（順序保持、N+1回避） | `BulkWordIdsRequest` | `list[WordRead]` |
| POST | `/check` | 単語リストの既存チェック | `BulkWordRequest` | `WordCheckResponse` |
| POST | `/check-inflection` | 入力語が活用形かどうかを検出し、lemma結合候補を提案 | `InflectionCheckRequest` | `InflectionCheckResponse` |
| PUT | `/{word_id}` | 単語名の変更（小文字化） | `WordCreateRequest` | `WordRead` |
| DELETE | `/{word_id}` | 単語削除（CASCADE、熟語行自体は残る） | — | — |
| POST | `/{word_id}/rescrape` | 既存単語の再スクレイプ＋GPT再構造化 | — | `WordRead` |
| POST | `/{word_id}/enrich-etymology` | 語源のcore_image/branchesのみ再補完 | — | `EtymologyRead` |
| PUT | `/{word_id}/definitions/{def_id}` | 定義1件の更新（例文含む） | `DefinitionUpdate` | `DefinitionRead` |
| PUT | `/{word_id}/full` | 単語の全項目手動編集（活用形・定義・語源・派生語・関連語・熟語） | `WordFullUpdate` | `WordRead` |
| PUT | `/{word_id}/etymology` | 語源サブグラフ全体の置き換え | `EtymologyUpdate` | `EtymologyRead` |
| POST | `/{word_id}/derivations` | 派生語の追加（カンマ区切りで複数同時追加可） | `DerivationCreate` | `list[DerivationRead]` |
| PUT | `/{word_id}/derivations/{der_id}` | 派生語の更新 | `DerivationUpdate` | `DerivationRead` |
| DELETE | `/{word_id}/derivations/{der_id}` | 派生語の削除 | — | — |
| POST | `/{word_id}/related-words` | 関連語の追加 | `RelatedWordCreate` | `list[RelatedWordRead]` |
| PUT | `/{word_id}/related-words/{rel_id}` | 関連語の更新 | `RelatedWordUpdate` | `RelatedWordRead` |
| DELETE | `/{word_id}/related-words/{rel_id}` | 関連語の削除 | — | — |

登録パイプライン（POST ``）の詳細な処理フローは `features/01_word.md`、活用形統合（`inflection_action`／`check-inflection`）は `features/08_inflection_lemma_merge.md` を参照。

---

## chat（`/api`）— 12エンドポイント

単語／語源コンポーネント／グループ／熟語の4スコープに対するチャットセッション・メッセージCRUD。

| Method | Path | 概要 |
|---|---|---|
| GET | `/words/{word_id}/chat/sessions` | 単語スコープのセッション一覧 |
| POST | `/words/{word_id}/chat/sessions` | 単語スコープのセッション作成 |
| GET | `/etymology-components/{component_text}/chat/sessions` | 語源コンポーネントスコープのセッション一覧 |
| POST | `/etymology-components/{component_text}/chat/sessions` | 語源コンポーネントスコープのセッション作成 |
| GET | `/groups/{group_id}/chat/sessions` | グループスコープのセッション一覧 |
| POST | `/groups/{group_id}/chat/sessions` | グループスコープのセッション作成 |
| GET | `/phrases/{phrase_id}/chat/sessions` | 熟語スコープのセッション一覧 |
| POST | `/phrases/{phrase_id}/chat/sessions` | 熟語スコープのセッション作成 |
| PATCH | `/chat/sessions/{session_id}` | セッション名変更 |
| DELETE | `/chat/sessions/{session_id}` | セッション削除（204） |
| GET | `/chat/sessions/{session_id}/messages` | メッセージ一覧 |
| POST | `/chat/sessions/{session_id}/messages` | メッセージ送信。LLMエージェントループ（`answer_in_session`）を実行し `ChatReply`（ユーザー発言＋アシスタント返信）を返す。初回メッセージからセッションタイトルを自動生成 |

エージェントループ・ツール呼び出し・SAVEPOINTパターンの詳細は `features/06_chat.md` を参照。

---

## groups（`/api/groups`）— 11エンドポイント

| Method | Path | 概要 |
|---|---|---|
| GET | `` | グループ一覧（名前検索・ページング） |
| POST | `` | グループ作成（名前は `group_name_max_length` で長さ制限） |
| GET | `/{group_id}` | グループ取得 |
| PUT | `/{group_id}` | グループ更新 |
| DELETE | `/{group_id}` | グループ削除 |
| POST | `/{group_id}/items` | アイテム1件追加（`word`/`phrase`（ID or アドホックテキスト）/`example`） |
| POST | `/{group_id}/bulk-add-items` | 単語＋熟語のID配列を一括追加（重複スキップ件数を返す） |
| DELETE | `/{group_id}/items/{item_id}` | アイテム削除 |
| POST | `/{group_id}/suggest` | キーワードからのLLM候補提案 |
| POST | `/{group_id}/generate-image` | グループ画像生成 |
| GET | `/{group_id}/default-image-prompt` | 画像生成プロンプトのプレビュー |

AI提案パイプライン・タブ構成は `features/04_group.md`、画像生成は `features/07_image_generation.md` を参照。

---

## images（`/api`）— 4エンドポイント

| Method | Path | 概要 |
|---|---|---|
| POST | `/words/{word_id}/generate-image` | 単語の公式画像を生成 |
| GET | `/words/{word_id}/default-image-prompt` | 単語画像プロンプトのプレビュー |
| POST | `/phrases/{phrase_id}/generate-image` | 熟語の公式画像を生成 |
| GET | `/phrases/{phrase_id}/default-image-prompt` | 熟語画像プロンプトのプレビュー |

詳細は `features/07_image_generation.md` を参照。

---

## audio（`/api`）— 4エンドポイント

いずれも `openai_api_key` 未設定時は503を返す。

| Method | Path | 概要 |
|---|---|---|
| POST | `/words/{word_id}/generate-audio` | 単語の発音音声を生成 |
| POST | `/words/{word_id}/examples/{example_id}/generate-audio` | 例文の音声を生成 |
| POST | `/phrases/{phrase_id}/generate-audio` | 熟語の音声を生成 |
| POST | `/phrases/{phrase_id}/definitions/{definition_id}/generate-audio` | 熟語定義の例文音声を生成 |

TTSの仕組み自体は `backend/04_services.md` の `tts_service.py` を参照（リスニング機能の行音声生成とは別エンドポイント、そちらは `listening.py` 側にある）。

---

## listening（`/api/listening`）— 18エンドポイント

台本生成・音声・セッション・採点・分析まで、リスニング練習機能の全APIをこのルーターが担う。

| Method | Path | 概要 |
|---|---|---|
| GET | `/personas` | TTSペルソナ一覧 |
| GET | `/personas/{voice}/sample` | ペルソナのサンプル音声を取得（キャッシュ生成） |
| POST | `/scripts/random` | ランダム台本生成（トピック/レベル/話者数/対話形式） |
| POST | `/scripts/custom/analyze` | ユーザー貼り付けテキストを話者・行に解析 |
| POST | `/scripts/custom/confirm` | 解析済みカスタム台本を確定・保存 |
| POST | `/scripts/weak-review` | 過去の弱点語・弱点フレーズを狙った復習台本を生成 |
| GET | `/scripts/{script_id}` | 台本全体（話者・行・音声バリアント）を取得 |
| POST | `/lines/{line_id}/generate-audio` | 1行分の音声を合成（音声バリアント指定可） |
| GET | `/lines/{line_id}/audio-variants` | 1行のキャッシュ済み音声バリアント一覧 |
| POST | `/sessions` | セッション作成 |
| GET | `/sessions` | セッション一覧 |
| GET | `/sessions/{session_id}` | セッション取得 |
| PATCH | `/sessions/{session_id}` | ステップ・再生速度・ディクテーションレベル・ステータスの更新 |
| DELETE | `/sessions/{session_id}` | セッション削除（204） |
| POST | `/sessions/{session_id}/attempts` | ディクテーション試行の記録（単語単位で採点） |
| POST | `/sessions/{session_id}/read-aloud-grade` | 音声アップロード→Whisper文字起こし→採点＋LLM発音フィードバック |
| GET | `/analytics/weak-words` | 弱点語の集計統計 |
| GET | `/analytics/weak-phrases` | 弱点フレーズの集計統計 |

全体フローは `features/05_listening.md` を参照。

---

## phrases（`/api`）— 12エンドポイント

| Method | Path | 概要 |
|---|---|---|
| GET | `/phrases` | 熟語一覧（検索・ソート） |
| GET | `/phrases/{phrase_id}` | 熟語取得 |
| GET | `/phrases/{phrase_id}/words` | 熟語に紐づく構成語一覧 |
| POST | `/phrases` | 熟語作成（既存なら取得）＋Wiktionaryエンリッチ |
| POST | `/phrases/{phrase_id}/enrich` | Wiktionaryエンリッチの再実行 |
| POST | `/phrases/check` | 熟語リストの既存チェック |
| PUT | `/phrases/{phrase_id}` | 意味のみ更新 |
| PUT | `/phrases/{phrase_id}/full` | 意味・定義・構成語ID・Wiktionary関連配列の全項目更新 |
| DELETE | `/phrases/{phrase_id}` | 熟語削除 |
| GET | `/words/{word_id}/phrases` | 単語に紐づく熟語一覧 |
| POST | `/words/{word_id}/phrases` | 単語に熟語を紐付け＋エンリッチ |
| DELETE | `/words/{word_id}/phrases/{phrase_id}` | 単語と熟語の紐付け解除 |

詳細は `features/02_phrase.md` を参照。

---

## search（`/api/search`）— 1エンドポイント

| Method | Path | 概要 |
|---|---|---|
| GET | `/suggest` | ヘッダー検索バー向け、単語＋熟語を横断したサジェスト（先頭一致優先） |

---

## etymology_components（`/api/etymology-components`）— 4エンドポイント

| Method | Path | 概要 |
|---|---|---|
| GET | `` | 一覧（各コンポーネントを含む単語数付き、ページング） |
| GET | `/{component_text}` | キャッシュ済みコンポーネント取得 |
| POST | `/{component_text}` | 未登録なら作成（Wiktionaryスクレイプ） |
| POST | `/{component_text}/rescrape` | 強制再スクレイプ |

詳細は `features/03_etymology.md` を参照。

---

## migration（`/api/migration`）— 2エンドポイント

活用形統合（lemma/inflection）機能のための管理系エンドポイント。

| Method | Path | 概要 |
|---|---|---|
| GET | `/inflection/targets` | lemma未解決の単語一覧（ページング） |
| POST | `/inflection/apply` | `merge`/`link` 判断のバッチ適用（件数ごとの成功/スキップ/エラーを返す） |

詳細は `features/08_inflection_lemma_merge.md` を参照。
