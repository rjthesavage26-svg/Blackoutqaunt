#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="$project_dir/runtime"
log_dir="$runtime_dir/logs"
pid_dir="$runtime_dir/pids"
backend_port="${BACKEND_PORT:-8001}"
frontend_port="${FRONTEND_PORT:-5173}"

mkdir -p "$log_dir" "$pid_dir"

if [[ ! -x "$project_dir/backend/.venv/bin/uvicorn" ]]; then
  echo "FAIL backend virtual environment is missing. Follow README.md setup steps." >&2
  exit 1
fi

if [[ ! -d "$project_dir/frontend/node_modules" ]]; then
  echo "FAIL frontend dependencies are missing. Run npm install in frontend/." >&2
  exit 1
fi

stop_all() {
  echo
  echo "Stopping Blackout Quant..."
  for name in cloudflared keep-awake frontend strategy worker backend; do
    pid_file="$pid_dir/$name.pid"
    if [[ -f "$pid_file" ]]; then
      pid="$(<"$pid_file")"
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
      fi
      rm -f "$pid_file"
    fi
  done
}

trap stop_all INT TERM EXIT

start_process() {
  local name="$1"
  shift
  local pid_file="$pid_dir/$name.pid"
  local log_file="$log_dir/$name.log"

  echo "starting $name"
  (
    cd "$project_dir"
    "$@" >"$log_file" 2>&1
  ) &
  echo "$!" >"$pid_file"
  echo "$name pid=$(<"$pid_file") log=$log_file"
}

./scripts/stop-local-stack.sh >/dev/null 2>&1 || true

start_process backend "$project_dir/backend/.venv/bin/uvicorn" app.main:app --app-dir "$project_dir/backend" --host 127.0.0.1 --port "$backend_port"
start_process worker env PYTHONPATH="$project_dir/backend" "$project_dir/backend/.venv/bin/python" -m app.workers.analysis
start_process strategy env PYTHONPATH="$project_dir/backend" "$project_dir/backend/.venv/bin/python" -m app.workers.alpaca_strategy
start_process frontend npm --prefix "$project_dir/frontend" run dev -- --host 127.0.0.1 --port "$frontend_port"

if command -v caffeinate >/dev/null 2>&1; then
  start_process keep-awake caffeinate -dimsu
fi

echo
echo "Waiting for backend..."
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1:$backend_port/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS -X POST "http://127.0.0.1:$backend_port/bot/stop" >/dev/null 2>&1 || true

echo
echo "Blackout Quant is running locally."
echo "Dashboard: http://127.0.0.1:$frontend_port"
echo "Backend:   http://127.0.0.1:$backend_port"
echo
echo "The bot starts STOPPED. Press Start Bot in the dashboard when you want Alpaca Paper trading armed."
echo "Keep this window open while testing. Closing it stops the local stack."
echo

if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:$frontend_port"
fi

while true; do
  for name in backend worker strategy frontend; do
    pid_file="$pid_dir/$name.pid"
    if [[ ! -f "$pid_file" ]] || ! kill -0 "$(<"$pid_file")" 2>/dev/null; then
      echo "$name stopped unexpectedly. Check $log_dir/$name.log"
      exit 1
    fi
  done
  sleep 5
done
