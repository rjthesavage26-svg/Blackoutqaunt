from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.dashboard import DashboardSnapshot, DashboardTrade
from app.services.dashboard_repository import DashboardRepository

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/snapshot", response_model=DashboardSnapshot)
def read_dashboard_snapshot() -> DashboardSnapshot:
    # Read-only endpoint for the React dashboard. It does not change trades,
    # webhook behavior, strategy logic, or AI analysis records.
    repository = DashboardRepository(settings.database_path)
    return repository.get_snapshot()


@router.get("/trades/{trade_id}", response_model=DashboardTrade)
def read_dashboard_trade(trade_id: int) -> DashboardTrade:
    # The UI uses this when a user clicks a trade row to review full context.
    repository = DashboardRepository(settings.database_path)
    trade = repository.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found.")
    return trade
