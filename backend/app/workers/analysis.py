import argparse
import logging
import time

from app.core.config import settings
from app.db.sqlite import initialize_database
from app.main import configure_logging
from app.services.ai_analysis_worker import AIAnalysisWorker
from app.services.analysis_job_repository import AnalysisJobRepository
from app.db.sqlite import connect

LOGGER = logging.getLogger(__name__)


def run_once() -> bool:
    jobs = AnalysisJobRepository(settings.database_path)
    job = jobs.claim_next()
    if job is None:
        return False
    try:
        result = AIAnalysisWorker(settings.database_path).analyze_saved_trade(job["trade_id"])
        if result is None:
            raise LookupError(f"Trade {job['trade_id']} does not exist.")
        jobs.complete(job["id"])
        LOGGER.info("analysis_job_completed", extra={"trade_id": job["trade_id"]})
    except Exception as error:
        jobs.fail(job["id"], job["attempts"], settings.analysis_worker_max_attempts, str(error))
        LOGGER.exception("analysis_job_failed", extra={"trade_id": job["trade_id"]})
    return True


def regenerate_entry_analyses() -> int:
    """Append fresh analysis rows for every stored entry trade."""
    with connect(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT id
            FROM trades
            WHERE event_type = 'ENTRY'
            ORDER BY timestamp ASC, id ASC;
            """
        ).fetchall()

    worker = AIAnalysisWorker(settings.database_path)
    regenerated = 0
    for row in rows:
        if worker.analyze_saved_trade(row["id"]) is not None:
            regenerated += 1
            LOGGER.info("analysis_regenerated", extra={"trade_id": row["id"]})
    return regenerated


def main() -> None:
    parser = argparse.ArgumentParser(description="Blackout Quant durable AI analysis worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job")
    parser.add_argument(
        "--regenerate-all",
        action="store_true",
        help="Append fresh analysis rows for all stored entry trades and exit",
    )
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    configure_logging()
    initialize_database(settings.database_path)
    if args.regenerate_all:
        regenerated = regenerate_entry_analyses()
        LOGGER.info("analysis_regeneration_completed", extra={"reason": f"regenerated={regenerated}"})
        return
    if args.once:
        run_once()
        return
    LOGGER.info("analysis_worker_started")
    while True:
        if not run_once():
            time.sleep(max(0.2, args.poll_seconds))


if __name__ == "__main__":
    main()
