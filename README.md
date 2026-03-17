# English Etymology Dictionary

Personal dictionary app with:

- Meaning + examples
- Etymology map
- On-demand image generation
- Related words and derivations
- Word-specific chatbot

## Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Lint / Format

Backend:

```bash
cd backend
uv run ruff check .
uv run ruff format .
```

Frontend:

```bash
cd frontend
npm run lint
npm run format
```

## Pre-commit

```bash
cd backend
uv run pre-commit install
uv run pre-commit run --all-files
```

