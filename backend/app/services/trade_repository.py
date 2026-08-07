import json
from pathlib import Path

from app.db.sqlite import connect
from app.models.tradingview import RawPayload, SavedTrade, TradingViewAlert


class TradeRepository:
    # A repository is a small object responsible for database work. Keeping SQL
    # here prevents API route files from becoming crowded as the project grows.
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def save_tradingview_alert(
        self,
        alert: TradingViewAlert,
        raw_payload: RawPayload,
    ) -> SavedTrade:
        # Lists and dictionaries cannot be stored directly in SQLite columns, so
        # reason_codes and raw_payload are saved as JSON text.
        reason_codes_json = json.dumps(alert.reason_codes)
        raw_payload_json = json.dumps(raw_payload)

        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO trades (
                    ticker,
                    action,
                    price,
                    timestamp,
                    reason_codes,
                    vwap,
                    ema50,
                    ema200,
                    opening_range_high,
                    opening_range_low,
                    volume,
                    average_volume,
                    atr,
                    stop_loss,
                    take_profit, event_type, quantity, event_id,
                    raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    alert.ticker,
                    alert.action,
                    alert.price,
                    alert.timestamp.isoformat(),
                    reason_codes_json,
                    alert.vwap,
                    alert.ema50,
                    alert.ema200,
                    alert.opening_range_high,
                    alert.opening_range_low,
                    alert.volume,
                    alert.average_volume,
                    alert.atr,
                    alert.stop_loss,
                    alert.take_profit,
                    alert.event_type,
                    alert.quantity,
                    alert.event_id,
                    raw_payload_json,
                ),
            )

            trade_id = cursor.lastrowid

        return SavedTrade(
            id=trade_id,
            ticker=alert.ticker,
            action=alert.action,
            price=alert.price,
            timestamp=alert.timestamp,
            reason_codes=alert.reason_codes,
            vwap=alert.vwap,
            ema50=alert.ema50,
            ema200=alert.ema200,
            opening_range_high=alert.opening_range_high,
            opening_range_low=alert.opening_range_low,
            volume=alert.volume,
            average_volume=alert.average_volume,
            atr=alert.atr,
            stop_loss=alert.stop_loss,
            take_profit=alert.take_profit,
        )
