#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_dir="$project_dir/runtime"
pid_dir="$runtime_dir/pids"
backend_port="${BACKEND_PORT:-8001}"

echo "Blackout Quant local stack status"

for name in backend worker strategy frontend keep-awake cloudflared; do
  pid_file="$pid_dir/$name.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(<"$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "$name=running pid=$pid"
    else
      echo "$name=stopped stale_pid=$pid"
    fi
  else
    echo "$name=not-started"
  fi
done

if [[ -f "$runtime_dir/tunnel-url.txt" ]]; then
  tunnel_url="$(<"$runtime_dir/tunnel-url.txt")"
  echo "tunnel=$tunnel_url"
  echo "webhook=$tunnel_url/webhook/tradingview"
fi

if command -v curl >/dev/null 2>&1; then
  echo
  echo "health:"
  curl -fsS "http://127.0.0.1:$backend_port/health" || true
  echo
fi
