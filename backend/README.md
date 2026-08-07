# Blackout Quant Backend

This backend receives TradingView paper-trading alerts, saves immutable events
to SQLite, updates simulated paper positions, and queues educational AI Coach
analysis for entries.

It does not place real trades, connect to brokers, automate a browser, or build dashboard features.

## Run The FastAPI Server

From inside the `backend` folder:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
uvicorn app.main:app --reload
```

The server runs at:

```text
http://localhost:8000
```

## Webhook Endpoint

```text
POST /webhook/tradingview
```

Full local URL:

```text
http://localhost:8000/webhook/tradingview
```

The webhook URL is configured with environment variables:

```text
PUBLIC_BACKEND_URL=http://localhost:8000
TRADINGVIEW_WEBHOOK_PATH=/webhook/tradingview
```

Together, those produce:

```text
http://localhost:8000/webhook/tradingview
```

For production, set `PUBLIC_BACKEND_URL` to the public HTTPS domain that reaches
this FastAPI backend.

## Test The Endpoint Locally

With the server running, send a test alert:

```bash
curl -X POST http://localhost:8000/webhook/tradingview \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "QQQ",
    "action": "BUY",
    "price": 714.22,
    "time": "2026-06-25T09:46:00-04:00",
    "reason_codes": [
      "VWAP_LONG",
      "EMA_BULLISH",
      "ORB_BREAKOUT",
      "HIGH_VOLUME"
    ],
    "vwap": 713.85,
    "ema50": 712.4,
    "ema200": 709.8,
    "opening_range_high": 713.9,
    "opening_range_low": 710.25,
    "volume": 1850000,
    "average_volume": 1100000,
    "atr": 1.12,
    "stop_loss": 712.54,
    "take_profit": 717.58
  }'
```

A successful request returns HTTP 200 and the saved trade record. Repeated
payloads with the same `event_id` return HTTP 409 without a second paper fill.

After a valid entry trade is saved, the backend inserts an `analysis_jobs` row.
The separate durable worker claims available jobs, reads saved trade data, and
stores educational analysis in the `trade_ai_analyses` table. The HTTP request
process does not own analysis execution.

## What Gets Saved

Each valid alert is saved in SQLite with:

- `id`
- `ticker`
- `action`
- `price`
- `timestamp`
- `reason_codes`
- `vwap`
- `ema50`
- `ema200`
- `opening_range_high`
- `opening_range_low`
- `volume`
- `average_volume`
- `atr`
- `stop_loss`
- `take_profit`
- `raw_payload`

The market-context fields are optional for now. Older test payloads that only
include the basic alert fields still work.

Optional lifecycle fields are `event_type` (`ENTRY` or `EXIT`, default
`ENTRY`), `event_id` (idempotency key), and `quantity` (paper quantity).

The default database file is:

```text
backend/data/blackout_quant.db
```

## Connect TradingView Alerts

TradingView requires a public HTTPS webhook URL. Localhost is not reachable from
TradingView directly.

For Cloudflare Tunnel setup, see:

```text
backend/CLOUDFLARE_TUNNEL_README.md
```

### Local Development

1. Start the backend from inside the `backend` folder:

```bash
cd /Users/r3/BlackoutQuant/backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

2. Expose the local backend with a secure HTTPS tunnel. The tunnel should forward to:

```text
http://localhost:8000
```

3. Copy the public HTTPS tunnel URL.

4. In `.env`, set:

```text
APP_ENV=development
PUBLIC_BACKEND_URL=https://your-temporary-tunnel-url.example
TRADINGVIEW_WEBHOOK_PATH=/webhook/tradingview
```

5. Restart the backend so the new environment values are loaded.

6. The TradingView webhook URL is:

```text
https://your-temporary-tunnel-url.example/webhook/tradingview
```

### Production

1. Deploy the FastAPI backend behind HTTPS.

2. Configure production environment variables:

```text
APP_ENV=production
PUBLIC_BACKEND_URL=https://your-public-backend-domain.example
TRADINGVIEW_WEBHOOK_PATH=/webhook/tradingview
BACKEND_CORS_ORIGINS=https://your-dashboard-domain.example
WEBHOOK_SECRET=replace-with-a-long-random-secret
```

Production startup fails fast if the public backend URL is not HTTPS, the
webhook secret is missing or weak, CORS is wildcarded, or other unsafe runtime
settings are detected. Development still starts with warnings so local testing
and quick-tunnel acceptance remain practical.

3. Confirm the public endpoint is reachable:

```bash
curl https://your-public-backend-domain.example/health
```

4. The TradingView webhook URL is:

```text
https://your-public-backend-domain.example/webhook/tradingview
```

### TradingView Alert Setup

1. Open the `QQQ` chart in TradingView.
2. Use the `5m` timeframe.
3. Add the Blackout Quant Pine strategy to the chart.
4. Click `Alert`.
5. Set `Condition` to the Blackout Quant strategy.
6. Select `Any alert() function call`.
7. Enable `Webhook URL`.
8. Paste the configured public webhook URL:

```text
<PUBLIC_BACKEND_URL>/webhook/tradingview
```

9. Leave the message box empty. The Pine strategy creates the JSON payload.
10. Create the alert.

TradingView will send the existing JSON payload directly to `POST /webhook/tradingview`.

This module only receives and stores alerts. It does not execute trades.

## Dashboard Endpoints

The React dashboard uses read-only endpoints:

```text
GET /dashboard/snapshot
GET /dashboard/trades/{trade_id}
```

These endpoints read existing SQLite data. They do not modify webhook behavior,
trading logic, trade execution, or AI analysis history.

The snapshot also returns recorded open/closed positions, realized P&L, win rate,
profit factor, equity curve, drawdown, webhook delivery history, and durable job
status.

## Production Configuration

Set `WEBHOOK_SECRET` to require `X-Blackout-Secret`; TradingView can instead use
`/webhook/tradingview?secret=<value>` because it cannot set a custom header. Configure
`BACKEND_CORS_ORIGINS`, `PUBLIC_BACKEND_URL`, `LOG_LEVEL`, and
`PAPER_POSITION_NOTIONAL` explicitly. `/health` reports database readiness and
schema version; `/diagnostics` includes non-secret configuration warnings;
application logs are JSON lines.

## Durable AI Worker

Webhook entry events enqueue `analysis_jobs`; the HTTP process no longer owns
analysis execution. Run the worker separately:

```bash
../scripts/start-analysis-worker.sh
```

Jobs are claimed transactionally, retried with backoff, and stale worker locks
are recovered after five minutes.

`GET /diagnostics` includes `analysis_jobs` counts plus `analysis_queue`
operational details: oldest pending availability, pending age in seconds, stale
running-job count, and latest failed-job error.

After improving the deterministic explanation engine, append fresh analysis rows
for stored entry trades with:

```bash
cd backend
.venv/bin/python -m app.workers.analysis --regenerate-all
```

Historical trades are not changed; the dashboard uses the latest analysis row.

## Reports and Journal

```text
PUT /journal/trades/{trade_id}
GET /journal/trades/{trade_id}
GET /reports/trade-journal.csv
GET /reports/performance.json
GET /reports/performance.csv
GET /webhooks/deliveries
GET /webhooks/failures
GET /bot/state
POST /bot/start
POST /bot/stop
GET /execution/orders
GET /strategy/state
GET /strategy/signals
```

## Preflight

From the project root:

```bash
API_BASE_URL=http://127.0.0.1:8000 ./scripts/preflight.sh
```

The script performs non-destructive configuration, SQLite integrity, health,
diagnostics, and export checks. In `APP_ENV=production`, unsafe runtime
configuration fails preflight instead of silently starting an exposed service.

## Database Backups

Use `../scripts/backup-database.sh`. It uses SQLite's online backup command, so
WAL transactions are included; do not copy only the main `.db` file while the
application is running.

## AI Coach Worker

The AI Coach worker is documented in:

```text
backend/AI_WORKER_README.md
```
