import json
from pathlib import Path
from typing import Any

from app.db.sqlite import connect


class WebhookAuditRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def record(
        self,
        *,
        status: str,
        response_status: int,
        payload: dict[str, Any] | None,
        event_id: str | None = None,
        error_message: str | None = None,
        trade_id: int | None = None,
    ) -> int:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO webhook_deliveries (
                    event_id, status, payload, error_message, trade_id,
                    response_status, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    event_id,
                    status,
                    json.dumps(payload) if payload is not None else None,
                    error_message,
                    trade_id,
                    response_status,
                ),
            )
            return cursor.lastrowid

    def list_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, event_id, status, error_message, trade_id,
                       response_status, received_at, completed_at
                FROM webhook_deliveries
                ORDER BY received_at DESC, id DESC LIMIT ?;
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_failures(self, limit: int = 100) -> list[dict[str, Any]]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, event_id, status, error_message, trade_id,
                       response_status, received_at, completed_at
                FROM webhook_deliveries
                WHERE status != 'PROCESSED'
                ORDER BY received_at DESC, id DESC LIMIT ?;
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
