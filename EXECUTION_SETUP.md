# Execution Setup

Blackout Quant now runs as a standalone Alpaca Paper bot:

```text
Alpaca Market Data
  -> Blackout Quant multi-strategy worker
  -> local paper ledger
  -> Alpaca Paper bracket order
  -> dashboard audit
```

TradingView is no longer required for signal generation. The old webhook route
is still present for backward compatibility, but `TRADINGVIEW_ENABLED=false` is
the default.

## Execution Modes

### `internal_paper`

Default mode. Webhooks are recorded and Blackout Quant simulates positions in
SQLite. No external order is submitted.

```text
EXECUTION_MODE=internal_paper
```

### `alpaca_paper`

Submits market/bracket orders to Alpaca Paper Trading after the dashboard bot is
started. Entry orders include stop-loss and take-profit legs when the strategy
has those levels.

```text
EXECUTION_MODE=alpaca_paper
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets
ALPACA_API_KEY=your-paper-key
ALPACA_API_SECRET=your-paper-secret
```

Safety behavior:

- The adapter rejects non-paper Alpaca URLs.
- Missing Alpaca keys produce runtime warnings and fail production startup.
- Webhooks are still recorded when the bot is stopped.
- External paper orders are submitted only after pressing `Start Bot` or calling
  `POST /bot/start`.
- `POST /bot/stop` disables external order submission.
- External order attempts are stored in `execution_orders`.
- The standalone strategy worker records its status in `strategy_state`.

## Dashboard Controls

- `Start Bot` arms configured external paper execution.
- `Stop Bot` disables configured external paper execution.

In `internal_paper`, Start/Stop only changes bot state because there is no
external broker. In `alpaca_paper`, Start/Stop controls whether webhooks submit
orders to Alpaca Paper and whether the standalone strategy worker polls Alpaca
market data.

## Enabled Strategies

The bot watches multiple QQQ setups at the same time:

- `QQQ_ORB`: opening-range breakout/breakdown with VWAP, EMA, and volume confirmation.
- `VWAP_RECLAIM_REJECT`: VWAP reclaim long or VWAP rejection short with trend/volume confirmation.
- `EMA_TREND_PULLBACK`: trend pullback to EMA 50 with VWAP and volume confirmation.

Only one trade can be active at a time. If several strategies signal on the same
bar, the worker records every candidate, selects the highest score, rejects the
lower-ranked candidates, and submits only the selected signal.

## API Controls

```text
GET  /bot/state
POST /bot/start
POST /bot/stop
GET  /execution/orders
GET  /strategy/state
GET  /strategy/signals
```

## Recommended Paper Validation

1. Create Alpaca Paper API keys.
2. Set `EXECUTION_MODE=alpaca_paper`.
3. Start the local stack.
4. Run preflight.
5. Start the bot from the dashboard.
6. Confirm the standalone strategy worker reports `WATCHING`.
7. Confirm a qualified selected strategy signal creates exactly one Alpaca Paper order.
8. Reconcile positions daily.

Do not connect live capital until a separate live-broker adapter is explicitly
authorized and paper results have been validated over an extended sample.
