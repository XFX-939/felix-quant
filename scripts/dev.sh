#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
  npm install
fi
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://127.0.0.1:${API_PORT}}" npm run dev -- --hostname 127.0.0.1 --port "$WEB_PORT" &
WEB_PID=$!

cleanup() {
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Backend:  http://127.0.0.1:${API_PORT}"
echo "Frontend: http://127.0.0.1:${WEB_PORT}"
wait
