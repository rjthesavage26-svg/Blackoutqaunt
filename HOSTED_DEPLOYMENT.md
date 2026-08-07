# Hosted Deployment

This is the no-Cloudflare production shape for Blackout Quant.

## Target Flow

```text
Hosted dashboard URL
  -> Start Bot button
  -> Alpaca market-data polling worker
  -> multi-strategy QQQ signal engine
  -> local paper ledger
  -> Alpaca Paper orders
  -> dashboard trades, P&L, positions, logs, and exports
```

TradingView is not required for the active bot. The old webhook API remains
available for compatibility.

## What Runs in Production

The Docker image starts three processes:

- FastAPI web server
- Durable AI analysis worker
- Alpaca strategy worker

If any process exits, the container exits so the hosting platform restarts the
whole service. SQLite is stored on a persistent disk at:

```text
/var/lib/blackout-quant/blackout_quant.db
```

## Render Deployment

The repository includes `render.yaml` for a Render Docker web service with a
persistent disk.

Required secret environment variables:

```text
ALPACA_API_KEY
ALPACA_API_SECRET
```

Important production variables:

```text
APP_ENV=production
EXECUTION_MODE=alpaca_paper
DATABASE_URL=sqlite:////var/lib/blackout-quant/blackout_quant.db
TRADINGVIEW_ENABLED=false
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets
ALPACA_DATA_BASE_URL=https://data.alpaca.markets
ALPACA_DATA_FEED=iex
STRATEGY_SYMBOL=QQQ
STRATEGY_POLL_SECONDS=30
PAPER_STARTING_CASH=100000
PAPER_POSITION_NOTIONAL=10000
PAPER_SLIPPAGE_BPS=1
PAPER_COMMISSION_PER_ORDER=0
```

After Render creates the service URL, update these values to that exact URL:

```text
BACKEND_CORS_ORIGINS=https://your-render-service.onrender.com
PUBLIC_BACKEND_URL=https://your-render-service.onrender.com
```

## Deploy Steps

1. Put this project in a Git repository and push it to GitHub.
2. In Render, create a new Blueprint from the repository.
3. Confirm the persistent disk is enabled.
4. Add `ALPACA_API_KEY` and `ALPACA_API_SECRET` as secret environment variables.
5. Deploy.
6. Open the Render URL.
7. Confirm the dashboard says the backend is reachable and `Mode: alpaca_paper`.
8. Click `Start Bot`.

## Operating Rules

- Leave the bot stopped until you intentionally start a paper session.
- Use Alpaca Paper only. Do not set a live Alpaca base URL.
- Review the dashboard after every session.
- Export the trade journal and performance report after each paper test day.
- Stop the bot before changing strategy or risk settings.

## Verification

Health:

```bash
curl https://your-render-service.onrender.com/health
```

Dashboard API:

```bash
curl https://your-render-service.onrender.com/api/dashboard/snapshot
```

Bot state:

```bash
curl https://your-render-service.onrender.com/api/bot/state
```

Do not move to live trading from this deployment. Live broker execution requires
a separately authorized adapter, account-risk limits, reconciliation alerts,
kill-switch testing, and extended paper-trading validation.
