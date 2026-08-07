#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="$project_dir/backend"
python_bin="$backend_dir/.venv/bin/python"
api_base_url="${API_BASE_URL:-http://127.0.0.1:${BACKEND_PORT:-8000}}"

if [[ ! -x "$python_bin" ]]; then
  echo "FAIL backend virtual environment is missing: $python_bin" >&2
  exit 1
fi

echo "Blackout Quant preflight"
echo "Project: $project_dir"
echo "API: $api_base_url"

cd "$backend_dir"

echo
echo "1. Static configuration and database checks"
"$python_bin" - <<'PY'
from app.core.config import settings
from app.db.sqlite import connect, initialize_database

errors = settings.production_errors()
warnings = settings.runtime_warnings()
initialize_database(settings.database_path)

with connect(settings.database_path) as connection:
    integrity = connection.execute("PRAGMA quick_check;").fetchone()[0]
    schema = connection.execute(
        "SELECT value FROM app_metadata WHERE key = 'schema_version';"
    ).fetchone()

print(f"database_path={settings.database_path}")
print(f"schema_version={schema['value'] if schema else 'unknown'}")
print(f"database_integrity={integrity}")
print(f"app_env={settings.app_env}")
print(f"paper_starting_cash={settings.paper_starting_cash}")
print(f"paper_position_notional={settings.paper_position_notional}")
print(f"paper_slippage_bps={settings.paper_slippage_bps}")
print(f"paper_commission_per_order={settings.paper_commission_per_order}")

if warnings:
    print("warnings:")
    for warning in warnings:
        print(f"- {warning}")
else:
    print("warnings=none")

if errors:
    print("production_errors:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

if integrity != "ok":
    raise SystemExit(1)
PY

echo
echo "2. HTTP health"
curl -fsS "$api_base_url/health"
echo

echo
echo "3. Diagnostics"
curl -fsS "$api_base_url/diagnostics"
echo

echo
echo "4. Export endpoints"
curl -fsS "$api_base_url/reports/performance.csv" >/dev/null
curl -fsS "$api_base_url/reports/trade-journal.csv" >/dev/null
echo "exports=ok"

echo
echo "Preflight passed."
