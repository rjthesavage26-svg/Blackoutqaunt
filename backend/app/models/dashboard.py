from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardAnalysis(BaseModel):
    # This model mirrors the AI Coach fields the dashboard needs to display.
    id: int | None = None
    trade_id: int | None = None
    trade_grade: str | None = None
    confidence_score: int | None = None
    plain_english_explanation: str | None = None
    why_the_trade_qualified: str | None = None
    risk_factors: str | None = None
    watch_after_entry: str | None = None
    educational_summary: str | None = None
    created_at: datetime | None = None


class DashboardTrade(BaseModel):
    # A read-only view of a saved trade plus its latest AI analysis.
    id: int
    ticker: str
    action: str
    price: float
    timestamp: datetime
    reason_codes: list[str]
    vwap: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    opening_range_high: float | None = None
    opening_range_low: float | None = None
    volume: float | None = None
    average_volume: float | None = None
    atr: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    outcome: str | None = None
    event_type: str = "ENTRY"
    realized_pnl: float | None = None
    analysis: DashboardAnalysis | None = None


class DashboardPosition(BaseModel):
    id: int
    ticker: str
    side: str
    status: str
    quantity: float
    entry_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime
    exit_price: float | None = None
    closed_at: datetime | None = None
    realized_pnl: float | None = None
    gross_pnl: float | None = None
    entry_commission: float = 0
    exit_commission: float = 0
    slippage_cost: float = 0
    close_reason: str | None = None


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
    cumulative_pnl: float
    drawdown: float
    drawdown_percent: float


class WebhookDelivery(BaseModel):
    id: int
    event_id: str | None = None
    status: str
    error_message: str | None = None
    trade_id: int | None = None
    response_status: int
    received_at: datetime
    completed_at: datetime | None = None


class AccountSummary(BaseModel):
    trades_today: int
    open_positions: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    average_reward_risk: float | None = None
    realized_pnl: float = 0
    profit_factor: float | None = None
    current_equity: float
    max_drawdown: float = 0
    max_drawdown_percent: float = 0


class AnalysisQueueSummary(BaseModel):
    counts: dict[str, int]
    oldest_available_at: datetime | None = None
    pending_age_seconds: float | None = None
    stale_running_jobs: int = 0
    latest_failure: str | None = None


class DashboardSnapshot(BaseModel):
    backend_status: str
    current_symbol: str
    current_session: str
    configuration_warnings: list[str] = []
    account: AccountSummary
    latest_trade: DashboardTrade | None
    trades: list[DashboardTrade]
    open_positions: list[DashboardPosition]
    closed_positions: list[DashboardPosition]
    equity_curve: list[EquityPoint]
    webhook_deliveries: list[WebhookDelivery]
    analysis_jobs: dict[str, int]
    analysis_queue: AnalysisQueueSummary | None = None
    bot_state: dict[str, Any] | None = None
    strategy_state: dict[str, Any] | None = None
    strategy_signals: list[dict[str, Any]] = []
    execution_orders: list[dict[str, Any]] = []


DashboardRawRow = dict[str, Any]
