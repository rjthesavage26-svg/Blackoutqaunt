import json
from pathlib import Path
from typing import Any

from app.db.sqlite import connect
from app.strategy.qqq_orb import StrategyDecision


class StrategySignalRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def record(self, *, decision: StrategyDecision, event_id: str, status: str, reason: str) -> None:
        if not decision.should_enter or not decision.action or not decision.price:
            return
        payload = {
            "reason_codes": decision.reason_codes,
            "vwap": decision.vwap,
            "ema50": decision.ema50,
            "ema200": decision.ema200,
            "opening_range_high": decision.opening_range_high,
            "opening_range_low": decision.opening_range_low,
            "volume": decision.volume,
            "average_volume": decision.average_volume,
            "atr": decision.atr,
            "message": decision.message,
        }
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO strategy_signals (
                    strategy_name, symbol, action, score, status, reason,
                    event_id, price, stop_loss, take_profit, source_payload
                ) VALUES (?, 'QQQ', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id, strategy_name) DO UPDATE SET
                    status = excluded.status,
                    reason = excluded.reason,
                    source_payload = excluded.source_payload;
                """,
                (
                    decision.strategy_name,
                    decision.action,
                    decision.score,
                    status,
                    reason,
                    event_id,
                    decision.price,
                    decision.stop_loss,
                    decision.take_profit,
                    json.dumps(payload),
                ),
            )

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, strategy_name, symbol, action, score, status, reason,
                       event_id, price, stop_loss, take_profit, created_at
                FROM strategy_signals
                ORDER BY created_at DESC, id DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
