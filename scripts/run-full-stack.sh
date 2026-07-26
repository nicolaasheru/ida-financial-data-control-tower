#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv. Create it with: python3 -m venv .venv"
  exit 1
fi

if [[ ! -d "dashboard/node_modules" ]]; then
  echo "Missing dashboard dependencies. Run: cd dashboard && npm install"
  exit 1
fi

bash scripts/sync-dashboard-data.sh

.venv/bin/python -m uvicorn backend.main:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000 &
api_pid=$!

cleanup() {
  kill "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd dashboard
npm run dev
