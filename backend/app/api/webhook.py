import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import ValidationError

from app.core.config import settings
from app.brokers.factory import get_execution_service
from app.models.tradingview import SavedTrade, TradingViewAlert
from app.services.analysis_job_repository import AnalysisJobRepository
from app.services.trade_repository import TradeRepository
from app.services.webhook_audit_repository import WebhookAuditRepository

router = APIRouter(prefix="/webhook", tags=["webhook"])
LOGGER = logging.getLogger(__name__)


@router.post("/tradingview", response_model=SavedTrade)
async def receive_tradingview_alert(
    request: Request,
    x_blackout_secret: str | None = Header(default=None),
    secret: str | None = Query(default=None),
) -> SavedTrade:
    audit = WebhookAuditRepository(settings.database_path)
    if settings.webhook_secret and settings.webhook_secret not in {x_blackout_secret, secret}:
        audit.record(status="REJECTED", response_status=401, payload=None, error_message="Invalid webhook secret.")
        LOGGER.warning("webhook_authentication_failed", extra={"client": request.client.host if request.client else None})
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    raw_payload: dict[str, Any] | None = None
    try:
        candidate = await request.json()
        if not isinstance(candidate, dict):
            raise ValueError("Webhook JSON must be an object.")
        raw_payload = candidate
        alert = TradingViewAlert.model_validate(raw_payload)
    except (ValueError, ValidationError) as error:
        audit.record(
            status="FAILED_VALIDATION",
            response_status=422,
            payload=raw_payload,
            error_message=str(error),
            event_id=raw_payload.get("event_id") if raw_payload else None,
        )
        raise HTTPException(status_code=422, detail="Invalid TradingView webhook payload.") from error

    # The repository handles the SQLite insert. The API route stays focused on
    # receiving the webhook and returning a clear success response.
    repository = TradeRepository(settings.database_path)
    try:
        saved_trade = repository.save_tradingview_alert(alert=alert, raw_payload=raw_payload)
    except sqlite3.IntegrityError as error:
        if alert.event_id:
            audit.record(
                status="DUPLICATE", response_status=409, payload=raw_payload,
                event_id=alert.event_id, error_message="Duplicate webhook event."
            )
            raise HTTPException(status_code=409, detail="Duplicate webhook event.") from error
        raise

    get_execution_service().process_alert(alert, saved_trade)

    if alert.event_type == "ENTRY":
        AnalysisJobRepository(settings.database_path).enqueue(saved_trade.id)

    audit.record(
        status="PROCESSED", response_status=200, payload=raw_payload,
        event_id=alert.event_id, trade_id=saved_trade.id,
    )

    LOGGER.info(
        "tradingview_webhook_accepted",
        extra={"trade_id": saved_trade.id, "event_type": alert.event_type, "ticker": alert.ticker},
    )

    return saved_trade
