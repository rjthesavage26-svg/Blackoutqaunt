from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.api.operations import router as operations_router
from app.core.config import settings
from app.db.sqlite import initialize_database

LOGGER = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("trade_id", "position_id", "event_type", "ticker", "reason", "realized_pnl"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=settings.log_level, handlers=[handler], force=True)


def validate_runtime_configuration() -> None:
    warnings = settings.runtime_warnings()
    for warning in warnings:
        LOGGER.warning("configuration_warning", extra={"reason": warning})

    errors = settings.production_errors()
    if errors:
        raise RuntimeError("Production configuration is unsafe: " + "; ".join(errors))


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    validate_runtime_configuration()
    initialize_database(settings.database_path)
    LOGGER.info(
        "application_started",
        extra={"environment": settings.app_env, "database_path": str(settings.database_path)},
    )
    yield


app = FastAPI(
    title=settings.app_name,
    description="Paper trading learning workstation API.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(webhook_router)
app.include_router(operations_router)
app.include_router(dashboard_router)
app.include_router(health_router, prefix="/api")
app.include_router(webhook_router, prefix="/api")
app.include_router(operations_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


@app.get("/", response_model=None)
def read_root():
    frontend_index = _frontend_index_path()
    if settings.app_env == "production" and frontend_index.exists():
        return FileResponse(frontend_index)

    return {
        "name": settings.app_name,
        "mode": "paper-trading-only",
        "message": "Blackout Quant backend is running.",
    }


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
def serve_dashboard(full_path: str):
    """Serve the built React dashboard for hosted single-URL deployments."""
    frontend_dist = _frontend_dist_path()
    index_path = frontend_dist / "index.html"
    requested_path = frontend_dist / full_path

    if settings.app_env != "production" or not index_path.exists():
        return {"detail": "Not Found"}

    if requested_path.is_file() and requested_path.resolve().is_relative_to(frontend_dist.resolve()):
        return FileResponse(requested_path)

    return FileResponse(index_path)


def _frontend_dist_path() -> Path:
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _frontend_index_path() -> Path:
    return _frontend_dist_path() / "index.html"
