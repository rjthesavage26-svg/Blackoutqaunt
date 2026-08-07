# Blackout Quant AI Coach Worker

The AI Coach worker creates an educational analysis for each saved paper trade.

It does not modify the TradingView strategy, execute trades, connect to brokers, or build dashboard features.

## Data Flow

```text
TradingView Alert
-> trades table
-> analysis_jobs durable queue
-> AI Coach worker process
-> trade_ai_analyses table
```

## How It Runs

1. TradingView sends a JSON alert to `POST /webhook/tradingview`.
2. The webhook validates the alert.
3. The webhook saves the trade in the `trades` table.
4. Entry alerts enqueue an `analysis_jobs` row.
5. The separate worker process transactionally claims an available job.
6. The worker reads the saved trade from SQLite.
7. The worker generates an educational analysis.
8. The analysis is inserted into `trade_ai_analyses`.
9. The job is marked `COMPLETED`, `RETRY`, or `FAILED`.

The webhook can still return HTTP 200 quickly because analysis execution is not
owned by the HTTP request process.

## Running The Durable Worker

From the repository root:

```bash
./scripts/start-analysis-worker.sh
```

For one-shot verification:

```bash
cd backend
.venv/bin/python -m app.workers.analysis --once
```

To append fresh analysis rows for every stored entry trade after improving the
deterministic explanation engine:

```bash
cd backend
.venv/bin/python -m app.workers.analysis --regenerate-all
```

This does not mutate trades or delete old explanations; the dashboard reads the
latest analysis row for each trade.

Jobs are retried with bounded exponential backoff. A `RUNNING` job whose lock is
older than five minutes is recovered automatically and returned to retryable
state.

Operational queue state is visible from:

```text
GET /diagnostics
```

The diagnostics response includes `analysis_jobs` status counts and
`analysis_queue` details such as oldest pending job age, stale running job count,
and the latest failed-job error.

## What The Worker Generates

For each saved trade, the worker stores:

- Trade grade, from `A` to `F`
- Confidence score, from `0` to `100`
- Plain-English explanation
- Why the trade qualified
- Risk factors
- What should be watched after entry
- Educational summary
- Source data snapshot used for the analysis

## What Data The Worker Uses

The worker only uses:

- Stored trade data from SQLite
- Blackout Quant strategy rules

If a field is missing, the worker explicitly says that the item cannot be determined from stored data.

For example, if `atr` was not included in the webhook payload, the risk section will say ATR cannot be reviewed because it was not stored.

## Regenerating Analysis Later

The original trade row is never changed by the AI Coach.

Each analysis is saved as a separate row linked by `trade_id`. This means explanations can be regenerated later by inserting a new `trade_ai_analyses` row for the same trade.

That design lets the project improve the explanation engine over time without rewriting historical trade records.

## Current Scope

This module uses a deterministic local worker. It does not call an external AI model yet.

Future modules may add a true AI model call, but the same database design can remain: original trade data stays in `trades`, and generated explanations stay in `trade_ai_analyses`.
