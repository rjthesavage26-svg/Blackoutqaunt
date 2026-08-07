# Blackout Quant Architecture

Blackout Quant is a paper-trading automation system. It has no live-broker
adapter and does not place real-money orders.

## Runtime Flow

```text
Alpaca Market Data
        |
        | 5-minute QQQ bars
        v
Standalone multi-strategy QQQ worker
        |
        v
SQLite trades
        |                  |
        |                  +--> durable analysis_jobs queue --> AI worker
        v
Execution service --> SQLite paper_positions
        |
        +--> optional Alpaca Paper order adapter
        |
        v
Dashboard API --> React dashboard (3-second polling)
```

The strategy worker evaluates QQQ ORB, VWAP reclaim/reject, and EMA trend
pullback setups at the same time. It records selected and rejected candidates in
`strategy_signals`, then submits only the highest-ranked selected signal when no
position is already open.

The execution service always maintains the local paper ledger. When
`EXECUTION_MODE=alpaca_paper` and the dashboard bot is running, it also submits
paper orders to Alpaca's paper API and audits the attempt in `execution_orders`.
Live execution must not be enabled without a separate security, reconciliation,
and risk review.

The TradingView webhook route remains available for backward compatibility only.
Set `TRADINGVIEW_ENABLED=true` if deliberately testing that optional path.

`BrokerAdapter` is the future broker contract. Reconciliation compares local
open paper positions against adapter-reported positions by ticker, side,
quantity, and average price. The harness is deliberately read-only and must not
submit orders during reconciliation.

## Data and Compatibility

- `trades`: immutable TradingView events and their original JSON payloads.
- `trade_ai_analyses`: reproducible analysis snapshots linked to entry events.
- `paper_positions`: position lifecycle, fills, costs, and net/gross P&L.
- `webhook_deliveries`: accepted, rejected, duplicate, and invalid deliveries.
- `analysis_jobs`: durable retryable AI analysis work.
- `trade_journal`: operator notes, mistakes, lessons, and tags.
- `bot_state`: dashboard-controlled execution arm/disarm state.
- `execution_orders`: external paper order submissions and failures.
- `app_metadata`: database schema version.

Schema version 3 migrates automatically at startup and retains existing rows.
Historical entries are not turned into positions because their close state
cannot be determined from stored data.

Original webhook payloads remain valid and default to `ENTRY`. New alerts add
`event_type`, optional `quantity`, and an idempotent `event_id`. Closed-position
analytics only use recorded entry and exit events; missing facts are not inferred.

## AI Analysis

The AI Coach is deterministic and uses saved trade data plus documented strategy
rules only. Missing inputs produce explicit “cannot be determined” language. It
does not predict outcomes or use unrecorded market context.

## Operations

`GET /health` reports database readiness and schema version. Logs are JSON lines.
Production must set `WEBHOOK_SECRET`; clients send `X-Blackout-Secret`, or
TradingView may use `?secret=<value>` because it cannot set a custom header.
Treat tunnel URLs as secrets and rotate them if exposed. Dashboard endpoints are
read-only. The AI worker runs separately with `scripts/start-analysis-worker.sh`.
`GET /diagnostics` reports database integrity, table counts, analysis job status
counts, non-secret configuration warnings, and queue-health details including
pending age, stale running locks, and the latest failed-job error. In
`APP_ENV=production`, unsafe public runtime settings fail startup instead of
only appearing as warnings.

Execution-cost settings model adverse slippage in basis points and a fixed
commission for each entry and exit order. Dashboard equity and drawdown use net
realized P&L only.

## Future Broker Integration

Add a live adapter beside `PaperBroker`, never inside webhook validation or the
dashboard repository. Before live capital, prove broker idempotency, order/fill
reconciliation, durable jobs, market-data validation, account risk limits,
managed secrets, audit retention, operational alerts, and a kill switch.

See `EXECUTION_SETUP.md` for paper execution setup and `LIVE_TRADING_GATE.md`
for the mandatory future live-capital gate.
