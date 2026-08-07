import json
from pathlib import Path
from typing import Any

from app.db.sqlite import connect


class ExecutionOrderRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def create_submitted(
        self,
        *,
        trade_id: int,
        client_order_id: str,
        execution_mode: str,
        broker: str,
        ticker: str,
        side: str,
        quantity: float,
        submitted_payload: dict[str, Any],
    ) -> int:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO execution_orders (
                    trade_id, client_order_id, execution_mode, broker, ticker,
                    side, quantity, status, submitted_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SUBMITTED', ?)
                ON CONFLICT(client_order_id) DO UPDATE SET
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
                """,
                (
                    trade_id,
                    client_order_id,
                    execution_mode,
                    broker,
                    ticker,
                    side,
                    quantity,
                    json.dumps(submitted_payload),
                ),
            )
            return cursor.fetchone()["id"]

    def mark_accepted(
        self,
        *,
        client_order_id: str,
        broker_order_id: str | None,
        response_payload: dict[str, Any],
        status: str = "ACCEPTED",
    ) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE execution_orders
                SET status = ?, broker_order_id = ?, response_payload = ?,
                    error_message = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE client_order_id = ?;
                """,
                (status, broker_order_id, json.dumps(response_payload), client_order_id),
            )

    def mark_rejected(self, *, client_order_id: str, error_message: str) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE execution_orders
                SET status = 'REJECTED', error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE client_order_id = ?;
                """,
                (error_message, client_order_id),
            )

    def list_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, trade_id, client_order_id, execution_mode, broker,
                       ticker, side, quantity, order_type, status,
                       broker_order_id, error_message, created_at, updated_at
                FROM execution_orders
                ORDER BY created_at DESC, id DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
