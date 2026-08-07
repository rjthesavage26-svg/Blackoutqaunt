#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

export APP_ENV="${APP_ENV:-production}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
export BACKEND_PORT="${PORT:-${BACKEND_PORT:-8000}}"
export PYTHONPATH="$project_dir/backend"

mkdir -p /var/lib/blackout-quant 2>/dev/null || true

shutdown() {
  for pid in "${pids[@]:-}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap shutdown TERM INT EXIT

pids=()

python -m app.workers.analysis &
pids+=("$!")

python -m app.workers.alpaca_strategy &
pids+=("$!")

uvicorn app.main:app \
  --host "$BACKEND_HOST" \
  --port "$BACKEND_PORT" \
  --workers "${BACKEND_WORKERS:-1}" \
  --proxy-headers &
pids+=("$!")

wait -n "${pids[@]}"
exit_code="$?"

shutdown
exit "$exit_code"
