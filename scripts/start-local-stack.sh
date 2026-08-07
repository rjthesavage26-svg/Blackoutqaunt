#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="$project_dir/runtime"
log_dir="$runtime_dir/logs"
pid_dir="$runtime_dir/pids"
backend_port="${BACKEND_PORT:-8001}"
frontend_port="${FRONTEND_PORT:-5173}"
start_tunnel="${START_TUNNEL:-0}"
keep_awake="${KEEP_AWAKE:-1}"
open_dashboard="${OPEN_DASHBOARD:-1}"

mkdir -p "$log_dir" "$pid_dir"

start_process() {
  local name="$1"
  shift
  local pid_file="$pid_dir/$name.pid"
  local log_file="$log_dir/$name.log"

  if [[ -f "$pid_file" ]]; then
    local existing_pid
    existing_pid="$(<"$pid_file")"
    if kill -0 "$existing_pid" 2>/dev/null; then
      echo "$name already running pid=$existing_pid"
      return 0
    fi
  fi

  echo "starting $name"
  (
    cd "$project_dir"
    nohup "$@" >"$log_file" 2>&1 < /dev/null &
    echo "$!" >"$pid_file"
  )
  echo "$name pid=$(<"$pid_file") log=$log_file"
}

if [[ ! -x "$project_dir/backend/.venv/bin/uvicorn" ]]; then
  echo "FAIL backend virtual environment is missing. Run backend setup from README.md." >&2
  exit 1
fi

if [[ ! -d "$project_dir/frontend/node_modules" ]]; then
  echo "FAIL frontend dependencies are missing. Run npm install in frontend/." >&2
  exit 1
fi

start_process backend "$project_dir/backend/.venv/bin/uvicorn" app.main:app --app-dir "$project_dir/backend" --host 127.0.0.1 --port "$backend_port"
start_process worker env PYTHONPATH="$project_dir/backend" "$project_dir/backend/.venv/bin/python" -m app.workers.analysis
start_process strategy env PYTHONPATH="$project_dir/backend" "$project_dir/backend/.venv/bin/python" -m app.workers.alpaca_strategy
start_process frontend npm --prefix "$project_dir/frontend" run dev -- --host 127.0.0.1 --port "$frontend_port"

if [[ "$keep_awake" == "1" ]]; then
  start_process keep-awake caffeinate -dimsu
fi

if [[ "$start_tunnel" == "1" ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    start_process cloudflared cloudflared tunnel --url "http://127.0.0.1:$backend_port"
  else
    echo "cloudflared not found; skipping tunnel"
  fi
fi

sleep 2

if [[ -f "$log_dir/cloudflared.log" ]]; then
  tunnel_url="$(grep -Eo 'https://[-a-zA-Z0-9]+\.trycloudflare\.com' "$log_dir/cloudflared.log" | tail -n 1 || true)"
  if [[ -n "${tunnel_url:-}" ]]; then
    echo "$tunnel_url" >"$runtime_dir/tunnel-url.txt"
    echo "tunnel=$tunnel_url"
    echo "webhook=$tunnel_url/webhook/tradingview"
    echo "IMPORTANT quick-tunnel URLs change after restart; use only for optional webhook testing."
  else
    echo "tunnel starting; check $log_dir/cloudflared.log for the URL"
  fi
fi

echo "dashboard=http://127.0.0.1:$frontend_port"
echo "backend=http://127.0.0.1:$backend_port"
if [[ "$open_dashboard" == "1" ]] && command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:$frontend_port"
fi
echo "Run ./scripts/status-local-stack.sh to inspect the stack."
