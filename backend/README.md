## Backend Setup (uv)

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Environment variables:

- Copy `.env.example` to `.env`
- Set `OPENAI_API_KEY` to enable GPT and image generation

## パッチスクリプト（登録単語のデータ一括再取得）

画像以外のデータ（語義・例文・語源・派生語・関連語など）を再スクレープ＋構造化で更新する。

```bash
cd backend
uv run python -m app.scripts.patch_refresh_word_data [--dry-run] [--limit N]
```

- `--dry-run`: 更新せずに対象単語を列挙するだけ
- `--limit N`: 先頭 N 件だけ処理（試すとき用）

## パッチスクリプト（コアイメージ/意味の分岐の補完）

登録済み単語の語源マップ向けデータ（`core_image`, `branches`）を LLM で補完する。

```bash
cd backend
uv run python -m app.scripts.patch_enrich_etymology_map [--dry-run] [--limit N] [--word WORD] [--only-missing]
```

- `--dry-run`: 更新せずに処理結果だけ表示
- `--limit N`: 先頭 N 件だけ処理
- `--word WORD`: 指定した1単語のみ処理（完全一致・大文字小文字無視）
- `--only-missing`: `core_image` 未設定/汎用値 または `branches` 空の単語だけ処理

## Lint / Format

```bash
uv run ruff check .        # lint
uv run ruff check . --fix  # lint fix
uv run ruff format .       # format
```



## Data Directory

Runtime data is consolidated under the project-root data/ directory.

- data/db/data.db: SQLite DB
- data/images/: generated image files
- data/nltk_data/: NLTK cache

Legacy locations such as `backend/data.db`, `backend/app/static/images/`, and
`backend/.nltk_data/` are no longer used in this repository.

