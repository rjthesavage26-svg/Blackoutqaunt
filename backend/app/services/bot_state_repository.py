from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.sqlite import connect


class BotStateRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get(self) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM bot_state WHERE id = 1;").fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO bot_state (id, status, execution_mode, message)
                    VALUES (1, 'STOPPED', ?, 'Bot is stopped.');
                    """,
                    (settings.execution_mode,),
                )
                row = connection.execute("SELECT * FROM bot_state WHERE id = 1;").fetchone()
            elif row["execution_mode"] != settings.execution_mode:
                connection.execute(
                    """
                    UPDATE bot_state
                    SET execution_mode = ?, message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1;
                    """,
                    (
                        settings.execution_mode,
                        f"Execution mode updated to {settings.execution_mode}; bot remains {row['status']}.",
                    ),
                )
                row = connection.execute("SELECT * FROM bot_state WHERE id = 1;").fetchone()
        return dict(row)

    def start(self) -> dict[str, Any]:
        message = "Bot is armed for internal paper simulation."
        if settings.execution_mode == "alpaca_paper":
            message = "Bot is armed for Alpaca Paper order execution."
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO bot_state (id, status, execution_mode, message)
                VALUES (1, 'RUNNING', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = 'RUNNING',
                    execution_mode = excluded.execution_mode,
                    message = excluded.message,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (settings.execution_mode, message),
            )
            row = connection.execute("SELECT * FROM bot_state WHERE id = 1;").fetchone()
        return dict(row)

    def stop(self, message: str = "Bot is stopped.") -> dict[str, Any]:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO bot_state (id, status, execution_mode, message)
                VALUES (1, 'STOPPED', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = 'STOPPED',
                    execution_mode = excluded.execution_mode,
                    message = excluded.message,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (settings.execution_mode, message),
            )
            row = connection.execute("SELECT * FROM bot_state WHERE id = 1;").fetchone()
        return dict(row)

    def is_running(self) -> bool:
        return self.get()["status"] == "RUNNING"
