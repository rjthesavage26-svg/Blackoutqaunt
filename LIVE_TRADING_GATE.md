# Live Trading Gate

Live broker execution is intentionally unavailable. The execution factory always
returns the paper implementation, and configuration exposes no live mode.

Before a separately authorized live adapter may be evaluated, all of these gates
must be satisfied and documented:

- At least 90 calendar days of uninterrupted paper operation.
- Named Cloudflare tunnel or deployed HTTPS service with monitored uptime.
- Zero unexplained reconciliation differences during the validation window.
- Webhook duplicate, invalid, retry, and outage drills completed.
- Broker sandbox certification with idempotent client order IDs.
- Order, partial-fill, cancellation, rejection, and disconnect tests.
- Independent limits for order size, gross exposure, daily loss, and drawdown.
- Operator kill switch tested under load and network failure.
- Managed secrets, access audit, alerting, backups, and disaster recovery.
- Independent code, security, and trading-risk review.
- Explicit written user authorization for the exact broker and account.

The `BrokerAdapter` contract and reconciliation service are test scaffolding, not
authorization or an implementation of live trading.
