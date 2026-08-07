# Blackout Quant Pine Strategy

This folder contains the first TradingView strategy for Blackout Quant.

It is for paper trading and learning only. It does not connect to a broker, send real orders, bypass TradingView protections, or automate browser activity.

## Strategy File

- `blackout_quant_qqq_orb_strategy.pine`

## What It Does

The strategy is designed for:

- Symbol: `QQQ`
- Timeframe: `5 minutes`
- Trading window: `9:30 AM` to `11:30 AM` America/New_York
- Opening range window: `9:30 AM` to `9:45 AM` America/New_York

Long trades require:

- Price above VWAP
- EMA 50 above EMA 200
- Opening range breakout confirmation
- Volume at least `1.5x` the 20-bar average
- ATR-based stop loss
- Take profit at least `2:1` reward/risk

Short trades require:

- Price below VWAP
- EMA 50 below EMA 200
- Opening range breakdown confirmation
- Volume at least `1.5x` the 20-bar average
- ATR-based stop loss
- Take profit at least `2:1` reward/risk

Risk controls:

- One open position at a time
- Stop after 3 losing trades in one session
- Maximum daily loss of 3%
- Every trade has a stop loss and take profit

## How To Install In TradingView

1. Open TradingView.
2. Open the `QQQ` chart.
3. Set the chart timeframe to `5m`.
4. Open the Pine Editor.
5. Copy the full contents of `blackout_quant_qqq_orb_strategy.pine`.
6. Paste the code into the Pine Editor.
7. Click `Save`.
8. Click `Add to chart`.
9. Open the Strategy Tester to review paper-trading results.

## How To Create A TradingView Alert

The strategy uses Pine's `alert()` function to send JSON webhook messages when
an entry executes and when the simulated strategy position closes.

1. Make sure the FastAPI backend is running.
2. Expose the local backend with a secure public HTTPS tunnel.
3. The local endpoint that must be exposed is:

```text
http://localhost:8000/webhook/tradingview
```

4. In TradingView, click `Alert`.
5. Set `Condition` to this strategy.
6. Choose `Any alert() function call`.
7. Enable `Webhook URL`.
8. Paste the public HTTPS URL that forwards to:

```text
http://localhost:8000/webhook/tradingview
```

9. Leave the alert message box empty. The Pine script builds the JSON message itself.
10. Create the alert.

Alerts include `event_type` (`ENTRY` or `EXIT`) and `event_id`. The backend uses
`event_id` to reject duplicate deliveries. Original webhook fields remain intact.

Do not connect this alert to a real broker.

## Example JSON Alert Payloads

Example BUY alert:

```json
{
  "ticker": "QQQ",
  "action": "BUY",
  "price": 714.22,
  "time": "2026-06-25T09:46:00-0400",
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
}
```

Example SELL alert:

```json
{
  "ticker": "QQQ",
  "action": "SELL",
  "price": 713.1,
  "time": "2026-06-25T10:05:00-0400",
  "reason_codes": [
    "VWAP_SHORT",
    "EMA_BEARISH",
    "ORB_BREAKDOWN",
    "HIGH_VOLUME"
  ],
  "vwap": 713.8,
  "ema50": 712.1,
  "ema200": 714.4,
  "opening_range_high": 716.2,
  "opening_range_low": 713.25,
  "volume": 1925000,
  "average_volume": 1200000,
  "atr": 1.05,
  "stop_loss": 714.68,
  "take_profit": 709.95
}
```

## Important Boundary

This module is only the TradingView Pine Script strategy.

It intentionally does not include:

- Dashboard features
- Browser automation
- Real broker integrations
- Real-money trade execution
