# Feature 06. チャット＆function-callingツール

前提：`backend/02_database.md`（クラスタ5: チャット）、`backend/03_api.md`（chatセクション）、`backend/04_services.md`（`chat_service.py`/`chat_tools.py`）を読んでいること。**チャット機能の仕組みはこのファイルにのみ記述する**。単語・熟語・グループ・語源要素の各機能ファイルはここへリンクするのみで、内容を再掲しない。

## 4スコープのセッション構造

チャットセッション（`chat_sessions`）は「単語」「語源コンポーネント」「グループ」「熟語」の4スコープのいずれか1つに限定される（`ck_chat_sessions_scope` CHECK制約、詳細は `backend/02_database.md`）。スコープごとに `chat_service.py` が異なるコンテキスト構築関数（`build_word_context`/`build_component_context`/`build_group_context`/`build_phrase_context`）を持ち、それぞれのエンティティの意味・語源・関連データをLLMのシステムコンテキストに含める。

## エージェントループ

`POST /chat/sessions/{session_id}/messages` を受けると、`chat_service._run_agent_loop`（OpenAI Responses API）がツール呼び出しを含む複数ラウンドの対話を行い、`answer_in_session` が最終的な `ChatReply`（ユーザー発言＋アシスタント返信）を組み立てる。ラウンド数は `MAX_TOOL_ROUNDS` で上限がある。`openai_api_key` 未設定時や失敗時は、それまでに実行済みの書き込みツール結果を要約したフォールバック返信を返す。初回メッセージからセッションタイトルが自動生成される。

## 5つのツール

| ツール | 常時/スコープ限定 | 概要 |
|---|---|---|
| `lookup_word_data` | 常時 | 指定した単語名から `definitions`/`etymology`/`derivations`/`related_words` の特定フィールドをDBから取得 |
| `search_db` | 常時 | `word_spelling`/`etymology_components`/`definitions`（または`all`）を対象に、最大5パターンのOR/AND部分一致検索 |
| `search_web` | 常時 | DuckDuckGo検索（`dictionary`モード：辞書サイト優先バイアス／`general`モード）、最大3クエリ |
| `register_related_word` | **単語スコープのみ**（`session.word_id` が設定されている場合） | 現在の単語に新しい `RelatedWord` 行を書き込む。ユーザーの明示的な依頼がある場合のみ実行する旨がツール自体の説明に明記されている |
| `generate_chat_image` | **単語/熟語/グループスコープのみ**（`session.component_text` が設定されている＝語源コンポーネントチャットでは提供されない） | チャット内画像生成（下記参照、詳細対比は `features/07_image_generation.md`） |

**スコープ別availability早見表**

| スコープ | lookup_word_data | search_db | search_web | register_related_word | generate_chat_image |
|---|---|---|---|---|---|
| 単語 | ○ | ○ | ○ | ○ | ○ |
| 熟語 | ○ | ○ | ○ | × | ○ |
| グループ | ○ | ○ | ○ | × | ○ |
| 語源コンポーネント | ○ | ○ | ○ | × | × |

ツール実行時の例外は個別にキャッチされ、失敗しても会話全体を止めずJSON形式の `{"error": ...}` 文字列としてLLMに返される。

## SAVEPOINTパターン

DBに書き込みを行うツール（`register_related_word`）は、チャットターン全体のDBトランザクションとは独立した SQL SAVEPOINT（`db.begin_nested()`）内で実行される。これにより、ツール呼び出しが失敗しても、既にflush済みのユーザーメッセージや、それ以前の会話内容までロールバックされることはない。1回の書き込み失敗が会話全体を巻き込まないための防御的パターンである。

## チャット内画像生成

`generate_chat_image` ツールは、`image_service.generate_image_bytes`（`gpt-image-1`）を使ってLLMが自ら考えたプロンプト＋代替テキストからPNGを生成し、`data/images/chat-<uuid>.png` として保存、`/static/images/<file>` のURLを返す。LLMはこのURLをMarkdown画像記法（`![alt](/static/images/xxx.png)`）で自分の返信テキストに直接埋め込む。単語/熟語/グループの「公式画像」（`WordImage`等、永続的でDB管理される）とは異なり、この画像はエンティティに紐づく専用テーブルへは保存されず、チャットメッセージのMarkdown内に埋め込まれるのみである。両者の違いの詳細な対比表は `features/07_image_generation.md` を参照。

## フロントエンド共有ロジック

`ChatPanel.tsx` が全4スコープ共通のプレゼンテーション層（セッション選択/リネーム/削除、Markdownレンダリング、プリセット質問、入力欄）を提供し、`useChatPanel.ts`（`frontend/src/lib/useChatPanel.ts`）がデータ取得・送信・キャッシュ無効化を担う。`WordChatPanel`/`ComponentChatPanel`/`GroupChatPanel`/`PhraseChatPanel` はいずれも約40行程度の薄いラッパーで、渡す `lib/api.ts` の名前空間（`chatApi`/`componentChatApi`/`groupChatApi`/`phraseChatApi`）とタイトル・プリセット質問だけが異なる。`useChatPanel` は、アシスタント返信の `citations` に書き込み系ツール（`register_related_word` 等、`WRITE_TOOL_SOURCES`）の使用が含まれる場合、単語関連のクエリキャッシュを無効化して画面を再取得させる。

### Markdown画像レンダリングのワークアラウンド

アシスタントメッセージは `react-markdown`＋`remark-gfm` でレンダリングされ、`![alt](/static/...)` は通常の `<img>` になる。しかし、バックエンドが返すのはルート相対パス（`/static/...`）であり、そのままではフロントエンドの開発サーバー自身のオリジンに対して解決されてしまう。`ChatPanel.tsx` の `chatMarkdownUrlTransform` を `ReactMarkdown` の `urlTransform` として渡し、`/static/` を含むURLだけをAPIベースURL（`CHAT_API_BASE_URL`）でプレフィックスする。加えて、`mdast-util-to-hast` の `normalizeUri` がLLMの返す生成テキスト中の余分な引用符（`"`）を `%22` としてパーセントエンコードしてしまう問題があるため、一度デコードして前後の引用符文字を取り除いてから `defaultUrlTransform` を適用し、その後で `/static/...` プレフィックスを付与する。CSS側（`index.css`）で `.markdown-body img` をブロック要素・max-width 100%・角丸に整形している。
