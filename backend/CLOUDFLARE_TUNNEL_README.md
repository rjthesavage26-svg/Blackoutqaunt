# Cloudflare Tunnel Setup

Use Cloudflare Tunnel to expose the local FastAPI backend through a public HTTPS URL so TradingView can send webhook alerts to Blackout Quant.

This guide does not change trading logic, Pine Script, the webhook schema, the database, the dashboard, or trade execution behavior.

## 1. Install Cloudflare Tunnel

Cloudflare Tunnel is provided by the `cloudflared` command-line tool.

### macOS With Homebrew

```bash
brew install cloudflare/cloudflare/cloudflared
```

Confirm it installed:

```bash
cloudflared --version
```

## 2. Start The Blackout Quant Backend

In one terminal:

```bash
cd /Users/r3/BlackoutQuant/backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

The backend should be available locally at:

```text
http://localhost:8000
```

Check it:

```bash
curl http://localhost:8000/health
```

## 3. Login To Cloudflare

In a second terminal:

```bash
cloudflared tunnel login
```

This opens a browser window. Choose the Cloudflare account and domain you want to use.

## 4. Create A Named Tunnel

Create a tunnel for Blackout Quant:

```bash
cloudflared tunnel create blackout-quant
```

List tunnels to confirm it exists:

```bash
cloudflared tunnel list
```

## 5. Run The Tunnel

For a quick local development tunnel, run:

```bash
cloudflared tunnel --url http://localhost:8000
```

Cloudflare will print a public HTTPS URL that looks similar to:

```text
https://example-words.trycloudflare.com
```

Your webhook endpoint becomes:

```text
https://example-words.trycloudflare.com/webhook/tradingview
```

Keep this terminal running while testing TradingView alerts.

## 6. Verify The Public HTTPS URL

Replace the example URL with the URL printed by `cloudflared`:

```bash
curl https://example-words.trycloudflare.com/health
```

You should see a health response from the FastAPI backend.

Then test the webhook endpoint:

```bash
curl -X POST https://example-words.trycloudflare.com/webhook/tradingview \
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
    ]
  }'
```

A successful request returns HTTP 200 and a saved trade record.

## 7. Example TradingView Webhook URL

In TradingView, use the public HTTPS URL plus the existing webhook path:

```text
https://example-words.trycloudflare.com/webhook/tradingview
```

TradingView alert setup:

1. Open the `QQQ` chart.
2. Use the `5m` timeframe.
3. Add the Blackout Quant Pine strategy to the chart.
4. Create an alert.
5. Set condition to the Blackout Quant strategy.
6. Select `Any alert() function call`.
7. Enable `Webhook URL`.
8. Paste the Cloudflare webhook URL.
9. Leave the message box empty because the Pine strategy emits the JSON.
10. Create the alert.

## 8. Optional Environment Configuration

Update `.env` so your app documentation/config reflects the active tunnel:

```text
PUBLIC_BACKEND_URL=https://example-words.trycloudflare.com
TRADINGVIEW_WEBHOOK_PATH=/webhook/tradingview
```

Restart the backend after changing `.env`.

## Troubleshooting

### TradingView Does Not Reach The Webhook

Check that:

- The backend terminal is still running.
- The Cloudflare Tunnel terminal is still running.
- The TradingView webhook URL starts with `https://`.
- The webhook URL ends with `/webhook/tradingview`.
- The alert condition is set to `Any alert() function call`.
- The TradingView message box is empty.

### `curl /health` Works Locally But Not Through Cloudflare

Restart the tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```

Use the new public URL printed by Cloudflare.

### Webhook Returns A Validation Error

The backend accepts the existing schema only. The JSON must include:

- `ticker`
- `action`
- `price`
- `time`
- `reason_codes`

Optional context fields may also be included, but payload field names must not be changed.

### Tunnel URL Changed

Quick tunnels using `trycloudflare.com` can change when restarted. If it changes, update the TradingView webhook URL.

For a stable production setup, use a named Cloudflare Tunnel with your own domain in Cloudflare.
