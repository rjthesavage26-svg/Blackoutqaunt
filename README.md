# Blackout Quant

Blackout Quant is an AI-powered Alpaca Paper trading workstation for learning
and extended paper validation.

This project is for education and paper trading only.

It does not connect to real brokers, place real-money trades, bypass TradingView protections, or automate live trading.

## Project Status

Task 1 complete: project skeleton.

Module 2 complete: first TradingView Pine Script paper strategy.

Module 3 complete: FastAPI webhook service that validates TradingView alerts and stores them in SQLite.

Module 4 complete: asynchronous AI Coach worker that stores educational trade analysis in a separate SQLite table.

Module 6 complete: React dashboard with read-only FastAPI endpoints for trades, account metrics, and AI analysis.

Module 7 complete: environment-based TradingView webhook URL configuration for local and production HTTPS endpoints.

Production foundation complete: versioned SQLite migration, idempotent webhook
events, structured logging, persisted paper-position lifecycle, realized P&L,
open/closed position views, and backend regression tests.

Production module expansion complete: TradingView/Cloudflare acceptance setup,
webhook audit/failure history, configurable slippage and commission modeling,
equity/drawdown analytics, durable AI jobs, trade-journal exports, and a broker
adapter/reconciliation contract.

The only execution implementation is deterministic paper trading. Live broker
integration and real-money trading logic remain intentionally unavailable.

## Tech Stack

- Python 3.14
- FastAPI
- SQLite
- React
- Vite
- Tailwind CSS
- Optional TradingView Pine Script v6 compatibility
- Alpaca Paper Trading
- Docker
- Git

## Folder Structure

```text
blackout-quant/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── services/
│   │   └── main.py
│   ├── data/
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── lib/
│   │   └── App.jsx
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── pine/
│   ├── README.md
│   └── blackout_quant_qqq_orb_strategy.pine
├── .env.example
├── .env.production.example
├── .gitignore
├── package.json
└── requirements.txt
```

## Getting Started

### 1. Create Environment File

Copy the example environment file:

```bash
cp .env.example .env
```

### 2. Install Backend Dependencies

```bash
cd backend
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
```

### 3. Start the Backend

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

### 4. Install Frontend Dependencies

```bash
npm install
```

### 5. Start the Frontend

```bash
npm run dev
```

The app will be available at:

```text
http://localhost:5173
```

## Backend Endpoints

- `GET /` returns a basic application message.
- `GET /health` returns backend and database health information.
- `GET /diagnostics` returns non-secret database and runtime diagnostics.
- `GET /bot/state` returns execution bot state.
- `POST /bot/start` arms configured external paper execution.
- `POST /bot/stop` disables configured external paper execution.
- `GET /execution/orders` returns external execution attempts.
- `GET /webhooks/deliveries` returns webhook processing history.
- `GET /webhooks/failures` returns rejected, duplicate, and failed webhook deliveries.
- `PUT /journal/trades/{trade_id}` stores journal notes and lessons.
- `GET /reports/trade-journal.csv` exports the trade journal.
- `GET /reports/performance.json` exports the dashboard/performance snapshot.
- `GET /reports/performance.csv` exports account-level performance metrics.
- `POST /webhook/tradingview` validates and stores TradingView paper-trading alerts.
- `GET /dashboard/snapshot` returns the read-only dashboard data.
- `GET /dashboard/trades/{trade_id}` returns one trade with its latest AI analysis.

See `ARCHITECTURE.md` for the current system design and compatibility guarantees.
The dashboard also surfaces non-secret runtime configuration warnings, so
development shortcuts such as missing webhook secrets or non-HTTPS public URLs
are visible before production.

Execution setup is documented in `EXECUTION_SETUP.md`. The primary system now
uses Alpaca market data, a Python multi-strategy QQQ worker, and Alpaca Paper
Trading. TradingView is optional/backward-compatible only.

## Operator Preflight

Run the non-destructive preflight before any extended paper-trading session:

```bash
API_BASE_URL=http://127.0.0.1:8000 ./scripts/preflight.sh
```

It validates configuration, initializes/migrates SQLite if needed, checks
database integrity, verifies `/health` and `/diagnostics`, and confirms report
exports are reachable.

## One-Command Local Stack

For local paper-trading sessions on this Mac:

```bash
./scripts/start-local-stack.sh
./scripts/status-local-stack.sh
./scripts/stop-local-stack.sh
```

The start script runs the backend, durable AI worker, standalone Alpaca strategy
worker, and frontend dashboard. Runtime logs and PIDs are written under
`runtime/`, which is intentionally ignored by git.

Cloudflare quick tunnels are no longer required for the standalone Alpaca bot.
Use `START_TUNNEL=1 ./scripts/start-local-stack.sh` only when deliberately
testing the optional TradingView webhook compatibility path.

## Hosted Deployment

Blackout Quant can run without Cloudflare as one hosted service. The production
container serves the React dashboard and FastAPI from the same public URL and
starts both durable background workers:

```text
Public dashboard URL
  -> FastAPI backend
  -> durable AI analysis worker
  -> Alpaca strategy worker
  -> Alpaca Paper Trading
  -> SQLite database on a persistent disk
```

The operator flow is:

1. Open the hosted dashboard URL.
2. Click `Start Bot`.
3. The worker watches Alpaca QQQ market data.
4. Qualified strategy setups submit Alpaca Paper orders.
5. The dashboard shows trades, positions, P&L, strategy candidates, logs, and exports.

Render deployment files are included:

- `Dockerfile`
- `render.yaml`
- `scripts/start-hosted-stack.sh`

See `HOSTED_DEPLOYMENT.md` for exact deployment steps and required environment
variables.

## TradingView Webhook Configuration

The webhook URL is configured through environment variables:

```text
PUBLIC_BACKEND_URL=http://localhost:8000
TRADINGVIEW_WEBHOOK_PATH=/webhook/tradingview
```

For local TradingView testing, expose the backend with a public HTTPS tunnel and
set `PUBLIC_BACKEND_URL` to that tunnel URL.

For production, set `PUBLIC_BACKEND_URL` to the deployed public HTTPS backend
domain. When `APP_ENV=production`, startup fails fast if `PUBLIC_BACKEND_URL`
is not HTTPS, `WEBHOOK_SECRET` is missing or weak, CORS is wildcarded, or other
unsafe runtime settings are detected.

TradingView Alert setup:

1. Open `QQQ` on the `5m` timeframe.
2. Add the Blackout Quant strategy to the chart.
3. Create an alert from the strategy report with condition
   `Order fills and alert() function calls`.
4. Enable webhook URL.
5. Use `<PUBLIC_BACKEND_URL>/webhook/tradingview`.
6. Leave the TradingView message box empty because the Pine strategy emits JSON.

The Pine strategy emits both entry and exit lifecycle events. Existing
entry-only webhook payloads remain valid.

Cloudflare Tunnel setup is documented in:

```text
backend/CLOUDFLARE_TUNNEL_README.md
```

Production-style startup and complete verification are available through:

```bash
./scripts/start-production.sh
./scripts/start-analysis-worker.sh
./scripts/verify.sh
./scripts/backup-database.sh
```

The API and analysis worker are separate durable processes. Run both in
production. Analysis jobs survive process restarts and retry with backoff.

Local runtime artifacts are intentionally excluded from source/deployment
packages: SQLite databases, WAL/SHM files, Python caches, `node_modules`, and
frontend build output. Use `scripts/backup-database.sh` before moving or
upgrading a long-running paper-trading database.

Paper execution costs are configured with:

```text
PAPER_SLIPPAGE_BPS=1
PAPER_COMMISSION_PER_ORDER=0
```

See `ACCEPTANCE_TEST.md` for the dated Cloudflare/TradingView acceptance record.

## SQLite

The SQLite database is created automatically when the FastAPI app starts.

By default, the database file lives at:

```text
backend/data/blackout_quant.db
```

## Paper Trading Boundary

Blackout Quant is intentionally scoped to learning and paper trading.

Future work may include simulated positions, journal entries, strategy notes, TradingView alert review, AI-assisted explanations, and Pine Script learning tools.

Future work must not include real broker execution or live-money automation.

## TradingView Strategy

The first paper strategy lives in:

```text
pine/blackout_quant_qqq_orb_strategy.pine
```

Installation instructions and example JSON alert payloads are documented in:

```text
pine/README.md
```
