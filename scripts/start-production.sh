#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir/backend"

if [[ ! -x .venv/bin/uvicorn ]]; then
  echo "Backend virtual environment is missing. Follow README.md installation steps." >&2
  exit 1
fi

export APP_ENV="${APP_ENV:-production}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

exec .venv/bin/uvicorn app.main:app \
  --host "${BACKEND_HOST:-127.0.0.1}" \
  --port "${BACKEND_PORT:-8000}" \
  --workers "${BACKEND_WORKERS:-1}" \
  --proxy-headers
