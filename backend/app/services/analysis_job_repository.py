from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.db.sqlite import connect


class AnalysisJobRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def enqueue(self, trade_id: int) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO analysis_jobs (trade_id) VALUES (?);",
                (trade_id,),
            )

    def claim_next(self) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        stale_before = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        with connect(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE;")
            connection.execute(
                """
                UPDATE analysis_jobs
                SET status = 'RETRY', locked_at = NULL,
                    last_error = COALESCE(last_error, 'Recovered stale worker lock.'),
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'RUNNING' AND locked_at < ?;
                """,
                (stale_before,),
            )
            row = connection.execute(
                """
                SELECT id, trade_id, attempts FROM analysis_jobs
                WHERE status IN ('PENDING', 'RETRY') AND available_at <= ?
                ORDER BY id LIMIT 1;
                """,
                (now,),
            ).fetchone()
            if row is None:
                return None
            updated = connection.execute(
                """
                UPDATE analysis_jobs
                SET status = 'RUNNING', locked_at = ?, attempts = attempts + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('PENDING', 'RETRY');
                """,
                (now, row["id"]),
            )
            if updated.rowcount != 1:
                return None
            return dict(row)

    def complete(self, job_id: int) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE analysis_jobs SET status = 'COMPLETED', completed_at = ?,
                    locked_at = NULL, last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (datetime.now(UTC).isoformat(), job_id),
            )

    def fail(self, job_id: int, attempts: int, max_attempts: int, error: str) -> None:
        terminal = attempts + 1 >= max_attempts
        available_at = datetime.now(UTC) + timedelta(seconds=min(300, 2 ** attempts))
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE analysis_jobs SET status = ?, last_error = ?, available_at = ?,
                    locked_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    "FAILED" if terminal else "RETRY",
                    error[:2000],
                    available_at.isoformat(),
                    job_id,
                ),
            )

    def status_counts(self) -> dict[str, int]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) count FROM analysis_jobs GROUP BY status;"
            ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    def operational_summary(self) -> dict[str, Any]:
        """Return non-secret queue diagnostics for health checks and runbooks."""
        now = datetime.now(UTC)
        stale_before = (now - timedelta(minutes=5)).isoformat()
        with connect(self.database_path) as connection:
            counts = self.status_counts()
            row = connection.execute(
                """
                SELECT
                    MIN(CASE WHEN status IN ('PENDING', 'RETRY') THEN available_at END)
                        AS oldest_available_at,
                    SUM(CASE WHEN status = 'RUNNING' AND locked_at < ? THEN 1 ELSE 0 END)
                        AS stale_running_jobs
                FROM analysis_jobs;
                """,
                (stale_before,),
            ).fetchone()
            failure_row = connection.execute(
                """
                SELECT last_error
                FROM analysis_jobs
                WHERE status = 'FAILED'
                ORDER BY updated_at DESC, id DESC
                LIMIT 1;
                """
            ).fetchone()

        oldest_available_at = row["oldest_available_at"] if row else None
        pending_age_seconds: float | None = None
        if oldest_available_at:
            try:
                oldest = datetime.fromisoformat(oldest_available_at)
                if oldest.tzinfo is None:
                    oldest = oldest.replace(tzinfo=UTC)
                pending_age_seconds = max(0.0, (now - oldest).total_seconds())
            except ValueError:
                pending_age_seconds = None

        return {
            "counts": counts,
            "oldest_available_at": oldest_available_at,
            "pending_age_seconds": pending_age_seconds,
            "stale_running_jobs": int(row["stale_running_jobs"] or 0) if row else 0,
            "latest_failure": failure_row["last_error"] if failure_row else None,
        }
