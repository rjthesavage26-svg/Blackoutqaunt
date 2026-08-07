import csv
import io
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.db.sqlite import connect
from app.models.journal import JournalEntry, JournalUpdate
from app.services.dashboard_repository import DashboardRepository
from app.services.bot_state_repository import BotStateRepository
from app.services.execution_order_repository import ExecutionOrderRepository
from app.services.strategy_state_repository import StrategyStateRepository
from app.services.strategy_signal_repository import StrategySignalRepository
from app.services.journal_repository import JournalRepository
from app.services.webhook_audit_repository import WebhookAuditRepository

router = APIRouter(tags=["operations"])


@router.get("/webhooks/deliveries")
def webhook_deliveries(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return WebhookAuditRepository(settings.database_path).list_recent(limit)


@router.get("/webhooks/failures")
def webhook_failures(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return WebhookAuditRepository(settings.database_path).list_failures(limit)


@router.get("/bot/state")
def bot_state() -> dict:
    return BotStateRepository(settings.database_path).get()


@router.get("/strategy/state")
def strategy_state() -> dict:
    return StrategyStateRepository(settings.database_path).get()


@router.get("/strategy/signals")
def strategy_signals(limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    return StrategySignalRepository(settings.database_path).list_recent(limit)


@router.post("/bot/start")
def start_bot() -> dict:
    return BotStateRepository(settings.database_path).start()


@router.post("/bot/stop")
def stop_bot() -> dict:
    return BotStateRepository(settings.database_path).stop()


@router.get("/execution/orders")
def execution_orders(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict]:
    return ExecutionOrderRepository(settings.database_path).list_recent(limit)


@router.get("/journal/trades/{trade_id}", response_model=JournalEntry)
def get_journal(trade_id: int) -> JournalEntry:
    entry = JournalRepository(settings.database_path).get(trade_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    return entry


@router.put("/journal/trades/{trade_id}", response_model=JournalEntry)
def update_journal(trade_id: int, update: JournalUpdate) -> JournalEntry:
    entry = JournalRepository(settings.database_path).upsert(trade_id, update)
    if entry is None:
        raise HTTPException(status_code=404, detail="Trade not found.")
    return entry


@router.get("/reports/performance.json")
def performance_report() -> dict:
    return DashboardRepository(settings.database_path).get_snapshot().model_dump(mode="json")


@router.get("/reports/performance.csv")
def performance_report_csv() -> StreamingResponse:
    snapshot = DashboardRepository(settings.database_path).get_snapshot()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    for key, value in snapshot.account.model_dump(mode="json").items():
        writer.writerow([key, value if value is not None else ""])
    writer.writerow(["configuration_warnings", " | ".join(snapshot.configuration_warnings)])
    writer.writerow([
        "analysis_pending_jobs",
        snapshot.analysis_queue.counts.get("PENDING", 0) if snapshot.analysis_queue else 0,
    ])
    writer.writerow([
        "analysis_failed_jobs",
        snapshot.analysis_queue.counts.get("FAILED", 0) if snapshot.analysis_queue else 0,
    ])
    writer.writerow(["webhook_deliveries_in_snapshot", len(snapshot.webhook_deliveries)])
    writer.writerow(["open_positions_in_snapshot", len(snapshot.open_positions)])
    writer.writerow(["closed_positions_in_snapshot", len(snapshot.closed_positions)])
    headers = {"Content-Disposition": "attachment; filename=blackout-quant-performance-report.csv"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/reports/trade-journal.csv")
def journal_export() -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "trade_id", "timestamp", "ticker", "action", "event_type", "price",
        "outcome", "realized_pnl", "grade", "confidence", "notes", "mistakes",
        "lessons", "tags",
    ])
    with connect(settings.database_path) as connection:
        rows = connection.execute(
            """
            SELECT t.id, t.timestamp, t.ticker, t.action, t.event_type, t.price,
                   p.realized_pnl, a.trade_grade, a.confidence_score,
                   j.notes, j.mistakes, j.lessons, j.tags
            FROM trades t
            LEFT JOIN paper_positions p ON p.entry_trade_id = t.id
            LEFT JOIN trade_ai_analyses a ON a.id = (
                SELECT id FROM trade_ai_analyses WHERE trade_id = t.id ORDER BY id DESC LIMIT 1
            )
            LEFT JOIN trade_journal j ON j.trade_id = t.id
            ORDER BY t.timestamp DESC, t.id DESC;
            """
        ).fetchall()
    for row in rows:
        pnl = row["realized_pnl"]
        outcome = "" if pnl is None else "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"
        writer.writerow([
            row["id"], row["timestamp"], row["ticker"], row["action"], row["event_type"],
            row["price"], outcome, pnl, row["trade_grade"], row["confidence_score"],
            row["notes"] or "", row["mistakes"] or "", row["lessons"] or "",
            ",".join(json.loads(row["tags"] or "[]")),
        ])
    headers = {"Content-Disposition": "attachment; filename=blackout-quant-trade-journal.csv"}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)
