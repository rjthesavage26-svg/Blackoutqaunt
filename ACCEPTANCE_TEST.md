# Acceptance Test Record

## August 6, 2026

Verified automatically:

- FastAPI started successfully with SQLite schema version 3.
- A temporary Cloudflare HTTPS tunnel returned HTTP 200 from `/health`.
- A labeled paper-only `ENTRY` event reached the backend through Cloudflare.
- A labeled paper-only `EXIT` event closed that position through Cloudflare.
- The resulting position produced recorded realized P&L.
- A schema-v3 repeat recorded `FAILED_VALIDATION`, `PROCESSED`, and `DUPLICATE`
  delivery history correctly.
- The durable worker claimed and completed the accepted entry analysis job.
- Dashboard visual acceptance confirmed equity, drawdown, closed positions,
  exports, webhook audit history, and worker status with live API data.
- No live broker was connected and no real-money order was submitted.

The initial quick tunnel returned HTTP 502 because it targeted a backend process
outside the tunnel process's reachable execution context. Starting the current
backend and tunnel in the same approved environment resolved the failure. This
is why production operations should use supervised services and a named tunnel.

TradingView loaded successfully in Chrome on August 6, 2026. After the user
signed in, the repository Pine script was pasted into Pine Editor and
successfully added to the QQQ 5-minute chart.

TradingView trial activation was completed by the user on August 6, 2026.
The checkout confirmation stated that the 30-day free trial is live, with
US $0.00 due immediately and the first paid renewal scheduled for
September 6, 2026.

A fresh Cloudflare quick tunnel was created and `/health` returned HTTP 200 at:

`https://brochures-constraint-naturals-least.trycloudflare.com/health`

The TradingView alert dialog was opened from the Blackout Quant strategy report
and verified to be configured for:

- Condition source: `BQ (...)`
- Trigger type: `Order fills and alert() function calls`
- Interval: `Same as chart 5 minutes`

The final webhook URL field remains blocked by TradingView account security:
TradingView displayed `Protect your data — To use webhooks, first enable
2-factor authentication.` This requires user-controlled account security setup
and cannot be completed safely by automation.

After the user indicated the account was ready, acceptance testing was retried
with another fresh quick tunnel. `/health` returned HTTP 200 at:

`https://ancient-background-bluetooth-stream.trycloudflare.com/health`

TradingView restored the chart session, the Blackout Quant strategy Add Alert
flow was opened again, and the alert condition again showed `BQ (...)`,
`Order fills and alert() function calls`, and `Same as chart 5 minutes`.
The webhook checkbox remained locked and TradingView again displayed the same
2-factor-authentication requirement. No TradingView webhook alert was created.

A third retry was started after the user indicated that one TradingView tab was
active and 2FA was enabled. A fresh quick tunnel was created and `/health`
returned HTTP 200 at:

`https://researchers-travelers-classification-retail.trycloudflare.com/health`

The old saved TradingView chart URL then returned `Chart Not Found`, so a fresh
TradingView chart was opened, switched to QQQ, and set to the 5-minute interval.
The repository Pine strategy was pasted into Pine Editor, but TradingView opened
a sign-in modal when adding the script to the chart. This indicates the Chrome
TradingView session was no longer authenticated for Pine/add-to-chart actions.
No TradingView webhook alert was created in this retry.

A fourth retry succeeded after the user restored the TradingView session:

- A replacement quick tunnel was created after one generated hostname did not
  resolve.
- `/health` returned HTTP 200 at
  `https://fashion-ancient-expert-driven.trycloudflare.com/health`.
- A fresh TradingView chart was loaded for `NASDAQ:QQQ`.
- The interval was set to 5 minutes.
- `pine/blackout_quant_qqq_orb_strategy.pine` was pasted into Pine Editor.
- The strategy compiled and was added to the chart.
- The chart showed `Paper strategy ready`.
- The strategy report Add Alert flow was used, keeping condition source `BQ (...)`.
- The alert was configured for `Order fills and alert() function calls`.
- The alert interval was `Same as chart 5 minutes`.
- Notifications were configured for `App, Toasts, Webhook`.
- Webhook URL:
  `https://fashion-ancient-expert-driven.trycloudflare.com/webhook/tradingview`
- TradingView showed `Alerts · 1 · Active strategy`, confirming the alert was
  created.

No real TradingView strategy fill occurred during the acceptance window, so no
TradingView-origin webhook delivery was observed yet. To verify the active
Cloudflare URL and backend audit path, a controlled non-TradingView acceptance
payload was sent through the same public webhook URL. It was accepted as
delivery `id=5`, status `PROCESSED`, trade `id=8`, event id
`acceptance-tv-alert-configured-20260806-162330`, and opened paper position
`id=3`.

## August 7, 2026 Follow-Up

Chrome inspection showed the QQQ chart, the Blackout Quant strategy, and
`Alerts · 1 · Active strategy`, but TradingView also displayed a session warning
that the account session ended because the account was accessed from another
browser or device. Treat the alert configuration as previously accepted, but do
not treat the active browser session as fully accepted again until the user
confirms the TradingView session is restored.

The active Cloudflare tunnel health check still returned HTTP 200 at:

`https://fashion-ancient-expert-driven.trycloudflare.com/health`

The local dashboard was reloaded and verified to show backend reachability,
runtime configuration warnings, equity/drawdown, export links, webhook delivery
audit, and durable worker status.

Once 2-factor authentication is enabled:

1. Open QQQ on 5 minutes.
2. Paste `pine/blackout_quant_qqq_orb_strategy.pine` into Pine Editor.
3. Save and add it to the chart; confirm zero compiler errors.
4. Open the strategy report and use its Add Alert control.
5. Confirm condition source `BQ (...)`.
6. Confirm trigger type `Order fills and alert() function calls`.
7. Use a current named Cloudflare webhook URL, not an expired quick-tunnel URL.
8. Leave the message blank unless deliberately testing TradingView placeholders.
9. Confirm a real strategy ENTRY and EXIT appear in the webhook delivery audit.
