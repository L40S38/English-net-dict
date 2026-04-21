#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "backend: uvicorn (http://127.0.0.1:8000)"
exec uv run --project "$ROOT/backend" \
    uvicorn server.main:app --app-dir "$ROOT/backend" --host 127.0.0.1 --port 8000
