#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/3] backend: uv sync"
(cd "$ROOT/backend" && uv sync)

echo "[2/3] frontend: npm ci"
echo "[3/3] frontend: npm run build"
(cd "$ROOT/frontend" && npm ci && npm run build)

echo "setup done. run ./start.sh to serve."
