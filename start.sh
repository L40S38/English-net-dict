#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

echo "frontend: building dist..."
(cd "$ROOT/frontend" && npm run build)

echo "frontend: vite preview (http://${FRONTEND_HOST}:${FRONTEND_PORT})"
(cd "$ROOT/frontend" && npx vite preview --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" --strictPort) &
FRONTEND_PID=$!

cleanup() {
    if kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

echo "backend: uvicorn (http://${BACKEND_HOST}:${BACKEND_PORT})"
uv run --project "$ROOT/backend" \
    uvicorn server.main:app --app-dir "$ROOT/backend" --host "$BACKEND_HOST" --port "$BACKEND_PORT"
