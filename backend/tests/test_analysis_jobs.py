from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db.sqlite import connect, initialize_database
from app.services.analysis_job_repository import AnalysisJobRepository


def test_analysis_job_operational_summary_reports_queue_state(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.db"
    initialize_database(database_path)
    repository = AnalysisJobRepository(database_path)
    stale_lock_time = (datetime.now(UTC) - timedelta(minutes=6)).isoformat()
    recent_failure_time = datetime.now(UTC).isoformat()

    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO trades (
                id, ticker, action, price, timestamp, reason_codes, raw_payload, event_type
            ) VALUES
                (1, 'QQQ', 'BUY', 100, '2026-08-06T10:00:00-04:00', '["TEST"]', '{}', 'ENTRY'),
                (2, 'QQQ', 'BUY', 101, '2026-08-06T10:05:00-04:00', '["TEST"]', '{}', 'ENTRY'),
                (3, 'QQQ', 'BUY', 102, '2026-08-06T10:10:00-04:00', '["TEST"]', '{}', 'ENTRY');
            """
        )
        connection.execute("INSERT INTO analysis_jobs (trade_id) VALUES (1);")
        connection.execute(
            """
            INSERT INTO analysis_jobs (trade_id, status, attempts, locked_at)
            VALUES (2, 'RUNNING', 1, ?);
            """,
            (stale_lock_time,),
        )
        connection.execute(
            """
            INSERT INTO analysis_jobs (trade_id, status, attempts, last_error, updated_at)
            VALUES (3, 'FAILED', 3, 'synthetic failure', ?);
            """,
            (recent_failure_time,),
        )

    summary = repository.operational_summary()

    assert summary["counts"] == {"FAILED": 1, "PENDING": 1, "RUNNING": 1}
    assert summary["oldest_available_at"] is not None
    assert summary["pending_age_seconds"] is not None
    assert summary["stale_running_jobs"] == 1
    assert summary["latest_failure"] == "synthetic failure"


def test_claim_next_recovers_stale_running_job(tmp_path: Path) -> None:
    database_path = tmp_path / "stale.db"
    initialize_database(database_path)
    repository = AnalysisJobRepository(database_path)
    stale_lock_time = (datetime.now(UTC) - timedelta(minutes=6)).isoformat()

    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO trades (
                id, ticker, action, price, timestamp, reason_codes, raw_payload, event_type
            ) VALUES (1, 'QQQ', 'BUY', 100, '2026-08-06T10:00:00-04:00', '["TEST"]', '{}', 'ENTRY');
            """
        )
        connection.execute(
            """
            INSERT INTO analysis_jobs (trade_id, status, attempts, locked_at, available_at)
            VALUES (1, 'RUNNING', 1, ?, ?);
            """,
            (stale_lock_time, stale_lock_time),
        )

    claimed = repository.claim_next()

    assert claimed is not None
    assert claimed["trade_id"] == 1
    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT status, attempts, locked_at, last_error FROM analysis_jobs WHERE trade_id = 1;"
        ).fetchone()
    assert row["status"] == "RUNNING"
    assert row["attempts"] == 2
    assert row["locked_at"] is not None
    assert row["last_error"] == "Recovered stale worker lock."
