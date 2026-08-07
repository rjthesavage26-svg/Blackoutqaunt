from typing import Protocol

from app.models.tradingview import SavedTrade, TradingViewAlert
from app.services.execution_service import TradingExecutionService


class ExecutionService(Protocol):
    def process_alert(self, alert: TradingViewAlert, trade: SavedTrade) -> None: ...


def get_execution_service() -> ExecutionService:
    """Return the configured paper execution coordinator."""
    return TradingExecutionService()
