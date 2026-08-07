from fastapi import APIRouter, Header, HTTPException, Query

from app.core.config import settings
from app.db.sqlite import connect, database_exists
from app.services.analysis_job_repository import AnalysisJobRepository

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    database_ready = False
    schema_version = "unknown"
    try:
        with connect(settings.database_path) as connection:
            row = connection.execute(
                "SELECT value FROM app_metadata WHERE key = 'schema_version';"
            ).fetchone()
            schema_version = row["value"] if row else "unknown"
            database_ready = True
    except Exception:
        database_ready = False
    return {
        "status": "ok" if database_ready else "degraded",
        "app": settings.app_name,
        "environment": settings.app_env,
        "database_ready": database_exists(settings.database_path) and database_ready,
        "schema_version": schema_version,
        "mode": "paper-trading-only",
    }


@router.get("/diagnostics")
def diagnostics(
    x_blackout_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
) -> dict[str, object]:
    """Return non-secret operational state for troubleshooting."""
    if settings.app_env == "production" and (
        not settings.webhook_secret
        or settings.webhook_secret not in {x_blackout_secret, secret}
    ):
        raise HTTPException(status_code=401, detail="Diagnostics authentication required.")
    with connect(settings.database_path) as connection:
        counts = {
            "trades": connection.execute("SELECT COUNT(*) FROM trades;").fetchone()[0],
            "analyses": connection.execute(
                "SELECT COUNT(*) FROM trade_ai_analyses;"
            ).fetchone()[0],
            "open_positions": connection.execute(
                "SELECT COUNT(*) FROM paper_positions WHERE status = 'OPEN';"
            ).fetchone()[0],
            "closed_positions": connection.execute(
                "SELECT COUNT(*) FROM paper_positions WHERE status = 'CLOSED';"
            ).fetchone()[0],
            "webhook_deliveries": connection.execute(
                "SELECT COUNT(*) FROM webhook_deliveries;"
            ).fetchone()[0],
        }
        integrity = connection.execute("PRAGMA quick_check;").fetchone()[0]

    analysis_jobs = AnalysisJobRepository(settings.database_path)
    return {
        "environment": settings.app_env,
        "mode": "paper-trading-only",
        "database_path": str(settings.database_path),
        "database_integrity": integrity,
        "webhook_path": settings.tradingview_webhook_path,
        "webhook_auth_configured": bool(settings.webhook_secret),
        "configuration_warnings": settings.runtime_warnings(),
        "counts": counts,
        "analysis_jobs": analysis_jobs.status_counts(),
        "analysis_queue": analysis_jobs.operational_summary(),
    }
