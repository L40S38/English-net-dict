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
uv run uvicorn server.main:app --reload --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Start Both (Single Command)

Run from the project root:

```bash
# PowerShell (Windows)
./start.ps1

# Bash (macOS / Linux / Git Bash)
./start.sh
```

This command runs backend dependency sync, frontend dependency install, frontend build, then starts FastAPI at `http://127.0.0.1:8000/` serving both API and built frontend.

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
