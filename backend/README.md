## Backend Setup (uv)

```bash
uv sync
uv run uvicorn server.main:app --reload --port 8000
```

Environment variables:

- Copy `.env.example` to `.env`
- Set `OPENAI_API_KEY` to enable GPT and image generation

## 統一 CLI (`database_build`)

`database_build` の更新系/検査系は統一 CLI から実行します。

```bash
cd backend

# 単語データ再取得
uv run python -m database_build word refresh --dry-run --limit 20

# 語源マップ補完（core_image / branches）
uv run python -m database_build etymology enrich-map --only-missing --limit 20

# 検査系
uv run python -m database_build inspect tables
uv run python -m database_build search --word hello
uv run python -m database_build preview refresh --word hello
```

旧 `patch_*.py` / `batch_*.py` は `database_build/tmp_script/` に退避し、
内部的に `database_build` CLI（= `ops` 実装）へ委譲します。

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

