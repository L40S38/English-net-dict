# Backend 04. サービス・プロンプト・LLM設定

前提：`00_overview.md`、`01_architecture.md` を読んでいること。ここは `core/services/` 配下の索引であり、個々のサービスがどう組み合わさって1機能を成すかは `features/` 側で説明する。

## サービス一覧（`backend/core/services/`）

| ファイル | 概要 | 関連機能 |
|---|---|---|
| `word_service.py` | 単語の読み取りモデル（`WordRead`/`EtymologyRead` の組み立て）とGPT構造化ペイロードのDB適用、語源コンポーネント/関連語/派生語の他単語へのリンク解決、`scrape_all`/`rescrape`/`enrich_etymology` の統括 | `features/01_word.md` |
| `word_ingest_service.py` | 単語・熟語の新規登録パイプライン全体（単語/熟語判定、4ソース同時スクレイプ、GPT構造化ペイロード構築） | `features/01_word.md` |
| `phrase_ingest_service.py` | Wiktionaryスクレイプ＋GPT翻訳から熟語の `PhraseDefinition` を構築 | `features/02_phrase.md` |
| `phrase_service.py` | `Phrase`/`WordPhrase` の低レベルCRUD（正規化・意味マージ・get-or-create・単語紐付け） | `features/02_phrase.md` |
| `chat_service.py` | スコープ別LLMコンテキスト構築、セッション/メッセージCRUD、ツール呼び出しエージェントループ | `features/06_chat.md` |
| `chat_tools.py` | function-callingツールの実装（`lookup_word_data`/`search_db`/`search_web`/`register_related_word`/`generate_chat_image`） | `features/06_chat.md` |
| `gpt_service.py` | 同期OpenAI呼び出し（単語構造化・例文補完・語源補完・熟語翻訳）、APIキー未設定時のルールベースフォールバック | `features/01_word.md` |
| `gpt_service_parallel.py` | 上記の非同期並列版（`AsyncOpenAI`使用） | `features/01_word.md` |
| `image_service.py` | 単語/グループ/熟語の画像生成プロンプト構築とOpenAI画像API呼び出し | `features/07_image_generation.md` |
| `tts_service.py` | OpenAI TTS/Whisperのラッパー（単語/例文/熟語音声生成、文字起こし、ペルソナサンプルキャッシュ） | `features/01_word.md`, `features/05_listening.md` |
| `listening_audio_service.py` | リスニング台本の行音声バリアント生成（`is_primary`管理） | `features/05_listening.md` |
| `listening_feedback_service.py` | 音読採点結果に対するLLM発音フィードバック生成 | `features/05_listening.md` |
| `listening_script_service.py` | ランダム/カスタム/弱点復習の台本生成、話者・行分割 | `features/05_listening.md` |
| `listening_session_service.py` | セッションのライフサイクル管理、ディクテーション/音読採点、弱点集計 | `features/05_listening.md` |
| `embedding_service.py` | OpenAI embeddingのローカルSQLiteキャッシュ | `features/01_word.md` |
| `definition_cluster_service.py` | embedding類似度による定義（意味）の重複統合クラスタリング | `features/01_word.md` |
| `group_suggest_service.py` | フリーテキストのキーワードから検索ルールを組み立て、候補をLLMで再ランキング | `features/04_group.md` |
| `word_merge_service.py` | 活用形単語をlemma単語にマージ、またはリンクのみ行う | `features/08_inflection_lemma_merge.md` |
| `lemma_service.py` | ある単語が既存の別単語の活用形かどうかを検出・スコアリング | `features/08_inflection_lemma_merge.md` |
| `etymology_component_service.py` | 語源コンポーネントテキストの正規化とキャッシュ行の取得/作成 | `features/03_etymology.md` |
| `phrase_meaning_service.py` | 熟語・関連語の日本語一行訳を得る共通カスケード処理（Wiktionary→WordNet→Web検索→LLM） | `features/01_word.md`, `features/02_phrase.md` |
| `spelling_suggestions.py` | `pyspellchecker` によるスペル候補提案 | `features/08_inflection_lemma_merge.md` |
| `web_word_search.py` | DuckDuckGo検索ラッパー（辞書サイト優先/一般検索の2モード） | `features/01_word.md`, `features/06_chat.md` |
| `wordnet_service.py` | NLTK WordNetの遅延ロードとシナプス/レンマのスナップショット抽出 | `features/01_word.md` |
| `example_cache.py` | GPT生成例文のSQLiteキャッシュ | `features/01_word.md` |
| `word_data_helpers.py` | 構造化ペイロードの正規化補助（活用形/熟語の重複排除、一行訳の補完） | `features/01_word.md` |

## スクレイパー一覧（`backend/core/services/scraper/`）

| ファイル | 概要 |
|---|---|
| `base.py` | 全スクレイパー共通の `BaseScraper`（httpx取得＋`compact_text`：BeautifulSoupでタグを剥がし1400文字に切り詰め） |
| `wiktionary.py` | MediaWiki API経由でWiktionaryの英語版・日本語版を並列取得し、定義・語源・活用形・関連語等を深く構造化して抽出する主要ソース |
| `wiktionary_parsers.py` | `wiktionary.py` に混ぜ込まれるパーサーMixin（品詞別定義・例文抽出など） |
| `etymology_extractors.py` | Wiktionaryの語源wikitext/テンプレート（`{{af}}`/`{{compound}}`/`{{suf}}`等）を構造化データに変換する純粋パース処理（ネットワークアクセスなし） |
| `etymonline.py` | etymonline.comの取得。構造化はせず、圧縮テキストのみをGPTへの補助情報として提供 |
| `eijiro.py` | 英辞郎（ALC）の取得。同上、補助テキストのみ |
| `weblio.py` | Weblioの取得。同上、補助テキストのみ |

4ソースの使われ方の違い（Wiktionaryのみ構造化パース、他3つは補助テキスト）の詳細は `features/01_word.md` を参照。

## LLM呼び出し方式

全てのLLM呼び出しは **OpenAI Responses API**（`client.responses.create`）経由で行われ、`chat.completions` は使用しない。また構造化出力（JSON Schemaモード）も使用せず、プレーンテキストとして返ってきたJSONを `_strip_json_code_fence` + `json.loads` + 独自の `repair_nested_strings`/`repair_text`（壊れたJSONを修復する自前ユーティリティ）でパースしている。使用するモデル名・用途別の設定値（`openai_model_structured`/`openai_model_chat`/`openai_image_model`/`openai_tts_model`/`openai_transcribe_model`）は `01_architecture.md` の設定表を参照（ここでは重複して記載しない）。

`gpt_service.py`（同期・`openai.OpenAI`）と `gpt_service_parallel.py`（非同期・`openai.AsyncOpenAI`）は互いに private関数をインポートして共有しており（例：`gpt_service_parallel.py` が `gpt_service._pick_forms` を再利用）、ロジックの二重実装を避けている。`listening_script_service.py`／`listening_feedback_service.py`／`phrase_meaning_service.py` も同じ Responses API パターンで直接LLMを呼び出す。

## プロンプトテンプレート一覧（`backend/core/prompts/`）

| ファイル | 概要 | 使用元 |
|---|---|---|
| `word_structuring.md` | WordNet＋スクレイプ結果から単語の構造化JSON（定義/活用形/語源/派生語/関連語）を生成 | `gpt_service.py` |
| `etymology_enrichment.md` | 語源の `core_image`/`branches` を補完 | `gpt_service.py` |
| `example_sentence.md` | 定義ごとの例文を1件生成 | `gpt_service.py` |
| `image_generation.md` | 単語の語源インフォグラフィック画像プロンプト | `image_service.py` |
| `group_image_generation.md` | グループ画像プロンプト | `image_service.py` |
| `phrase_image_generation.md` | 熟語画像プロンプト | `image_service.py` |
| `word_chat.md` | 単語チャットのシステムプロンプト | `chat_service.py` |
| `component_chat.md` | 語源コンポーネントチャットのシステムプロンプト | `chat_service.py` |
| `chat_agent.md` | ツール呼び出し可能な汎用チャットエージェントのシステムプロンプト | `chat_service.py` |
| `group_suggest_rules.md` | ユーザーの意図からDB検索ルールを生成 | `group_suggest_service.py` |
| `group_suggest_rerank.md` | 候補をルールに照らして絞り込み・再ランキング | `group_suggest_service.py` |
| `listening_script_generation.md` | TOEIC Part3/4形式のリスニング台本を生成 | `listening_script_service.py` |
| `listening_script_segmentation.md` | ユーザー貼り付けテキストを話者・行に分割 | `listening_script_service.py` |
| `read_aloud_feedback.md` | 音読の文字起こしから発音フィードバックを生成 | `listening_feedback_service.py` |

## スキーマ層概要（`core/schemas.py`）

Pydanticスキーマは対応するルーター・機能ごとにグルーピングされている（網羅列挙はしない）：単語/定義コア、語源、派生語/関連語、活用形統合、熟語、画像、語源コンポーネントキャッシュ/検索、グループ、検索、チャット、GPT構造化出力用の内部DTO（`StructuredWordPayload`等）、リスニング（最大のグループ）。個々のフィールドは対応する `backend/02_database.md` のテーブル定義、または `backend/03_api.md` の該当エンドポイントのRequest/Response要点を参照。

## 定数・パーソナ

`core/constants.py`：`group_name_max_length`（`config.yaml` 由来）等のアプリ全体の定数。

`core/personas.py`：リスニング機能で使う6種のTTSペルソナ。

| voice（OpenAI TTS音声ID） | 表示名 | 性別 | 説明 |
|---|---|---|---|
| `alloy` | Alex | neutral | 落ち着いた中性的な声。クセのないニュートラルな話し方 |
| `echo` | Ethan | male | はっきりとした男性の声。クリアな発音 |
| `fable` | Felix | male | 落ち着いた語り口調。英国風の響き |
| `onyx` | Owen | male | 低音でどっしりした男性の声。重厚で力強い印象 |
| `nova` | Nora | female | 明るくハキハキした女性の声。テンポが良い |
| `shimmer` | Sophie | female | 柔らかく軽やかな女性の声。優しく落ち着いた印象 |

利用方法の詳細は `features/05_listening.md` を参照。
