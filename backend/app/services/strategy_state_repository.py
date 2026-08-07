from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.sqlite import connect


class StrategyStateRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get(self) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM strategy_state WHERE id = 1;").fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO strategy_state (id, symbol, status, message)
                    VALUES (1, ?, 'IDLE', 'Strategy worker has not run yet.');
                    """,
                    (settings.strategy_symbol.upper(),),
                )
                row = connection.execute("SELECT * FROM strategy_state WHERE id = 1;").fetchone()
        return dict(row)

    def update(
        self,
        *,
        status: str,
        message: str,
        session_date: str | None = None,
        last_bar_at: str | None = None,
        opening_range_high: float | None = None,
        opening_range_low: float | None = None,
        latest_signal: str | None = None,
    ) -> dict[str, Any]:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO strategy_state (
                    id, symbol, status, session_date, last_bar_at,
                    opening_range_high, opening_range_low, latest_signal, message
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol = excluded.symbol,
                    status = excluded.status,
                    session_date = excluded.session_date,
                    last_bar_at = excluded.last_bar_at,
                    opening_range_high = excluded.opening_range_high,
                    opening_range_low = excluded.opening_range_low,
                    latest_signal = excluded.latest_signal,
                    message = excluded.message,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    settings.strategy_symbol.upper(),
                    status,
                    session_date,
                    last_bar_at,
                    opening_range_high,
                    opening_range_low,
                    latest_signal,
                    message,
                ),
            )
            row = connection.execute("SELECT * FROM strategy_state WHERE id = 1;").fetchone()
        return dict(row)
