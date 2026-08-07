#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$project_dir/backend"
.venv/bin/python -m compileall -q app
.venv/bin/python -m pytest -q

cd "$project_dir/frontend"
npm run build

if [[ -x "$project_dir/scripts/preflight.sh" ]]; then
  bash -n "$project_dir/scripts/preflight.sh"
fi

echo "Blackout Quant verification passed."
