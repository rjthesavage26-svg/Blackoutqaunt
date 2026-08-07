#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir/backend"

if [[ ! -x .venv/bin/python ]]; then
  echo "Backend virtual environment is missing. Follow README.md installation steps." >&2
  exit 1
fi

exec .venv/bin/python -m app.workers.analysis
