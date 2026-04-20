#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/4] backend: uv sync"
(cd "$ROOT/backend" && uv sync)

echo "[2/4] frontend: npm ci"
echo "[3/4] frontend: npm run build"
(cd "$ROOT/frontend" && npm run build)

echo "[4/4] backend: uvicorn (http://127.0.0.1:8000)"
exec uv run --project "$ROOT/backend" \
    uvicorn server.main:app --app-dir "$ROOT/backend" --host 127.0.0.1 --port 8000
