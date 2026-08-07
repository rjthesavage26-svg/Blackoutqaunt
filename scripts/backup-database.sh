#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
database_path="${1:-$project_dir/backend/data/blackout_quant.db}"
backup_path="${2:-$project_dir/backend/data/blackout_quant-backup-$(date +%Y%m%d-%H%M%S).db}"

if [[ ! -f "$database_path" ]]; then
  echo "Database not found: $database_path" >&2
  exit 1
fi

sqlite3 "$database_path" ".backup '$backup_path'"
sqlite3 "$backup_path" "PRAGMA quick_check;"
echo "$backup_path"
