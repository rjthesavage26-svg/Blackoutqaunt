#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pid_dir="$project_dir/runtime/pids"

for name in cloudflared frontend strategy worker backend; do
  pid_file="$pid_dir/$name.pid"
  if [[ ! -f "$pid_file" ]]; then
    continue
  fi
  pid="$(<"$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "stopping $name pid=$pid"
    kill "$pid"
  fi
  rm -f "$pid_file"
done

echo "Blackout Quant local stack stopped."
