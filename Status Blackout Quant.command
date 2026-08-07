#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

./scripts/status-local-stack.sh

echo
read -r -p "Press Return to close this window. "
