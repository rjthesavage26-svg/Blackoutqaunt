from pathlib import Path

from app.db.sqlite import connect, initialize_database
from app.services.ai_analysis_worker import AIAnalysisWorker
from app.workers.analysis import regenerate_entry_analyses
from app.core.config import settings


def insert_trade(
    database_path: Path,
    *,
    stop_loss: float | None,
    take_profit: float | None,
    atr: float | None = None,
) -> int:
    initialize_database(database_path)
    with connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO trades (
                ticker, action, price, timestamp, reason_codes, vwap, ema50, ema200,
                opening_range_high, opening_range_low, volume, average_volume, atr,
                stop_loss, take_profit, raw_payload, event_type
            ) VALUES (
                'QQQ', 'BUY', 100.0, '2026-08-06T10:00:00-04:00', '["TEST"]',
                99.0, 101.0, 98.0, 99.5, 97.0, 1500.0, 1000.0, ?, ?, ?, '{}', 'ENTRY'
            );
            """,
            (atr, stop_loss, take_profit),
        )
        return cursor.lastrowid


def test_ai_analysis_treats_exact_two_to_one_reward_risk_as_passing(tmp_path: Path) -> None:
    database_path = tmp_path / "ai-rr.db"
    trade_id = insert_trade(database_path, stop_loss=99.0, take_profit=102.0, atr=1.0)

    analysis = AIAnalysisWorker(database_path).analyze_saved_trade(trade_id)

    assert analysis is not None
    assert "Reward/risk must be at least 2:1" in analysis.why_the_trade_qualified
    assert "Reward/risk must be at least 2:1" not in analysis.risk_factors
    assert analysis.trade_grade == "A"


def test_ai_analysis_explicitly_marks_missing_values_as_unavailable(tmp_path: Path) -> None:
    database_path = tmp_path / "ai-missing.db"
    trade_id = insert_trade(database_path, stop_loss=None, take_profit=None, atr=None)

    analysis = AIAnalysisWorker(database_path).analyze_saved_trade(trade_id)

    assert analysis is not None
    assert "Cannot be determined from stored data" in analysis.why_the_trade_qualified
    assert "stop_loss was not stored" in analysis.risk_factors
    assert "take_profit was not stored" in analysis.risk_factors
    assert "ATR cannot be reviewed because atr was not stored" in analysis.risk_factors
    assert "Stop loss cannot be monitored from stored data" in analysis.watch_after_entry
    assert "Take profit cannot be monitored from stored data" in analysis.watch_after_entry


def test_regenerate_entry_analyses_appends_fresh_rows_for_entries_only(tmp_path: Path) -> None:
    database_path = tmp_path / "regenerate.db"
    original_database_url = settings.database_url
    try:
        settings.__dict__.pop("database_path", None)
        settings.database_url = f"sqlite:///{database_path}"
        entry_trade_id = insert_trade(database_path, stop_loss=99.0, take_profit=102.0, atr=1.0)
        with connect(database_path) as connection:
            connection.execute(
                """
                INSERT INTO trades (
                    ticker, action, price, timestamp, reason_codes, raw_payload, event_type
                ) VALUES (
                    'QQQ', 'SELL', 101.0, '2026-08-06T10:30:00-04:00', '["EXIT"]', '{}', 'EXIT'
                );
                """
            )

        regenerated = regenerate_entry_analyses()

        assert regenerated == 1
        with connect(database_path) as connection:
            rows = connection.execute(
                "SELECT trade_id FROM trade_ai_analyses ORDER BY id;"
            ).fetchall()
        assert [row["trade_id"] for row in rows] == [entry_trade_id]
    finally:
        settings.__dict__.pop("database_path", None)
        settings.database_url = original_database_url
