import json
from datetime import datetime
from pathlib import Path

from app.db.sqlite import connect
from app.models.dashboard import (
    AccountSummary,
    AnalysisQueueSummary,
    DashboardAnalysis,
    DashboardSnapshot,
    DashboardTrade,
    DashboardPosition,
    EquityPoint,
    WebhookDelivery,
)
from app.core.config import settings
from app.services.analysis_job_repository import AnalysisJobRepository
from app.services.bot_state_repository import BotStateRepository
from app.services.execution_order_repository import ExecutionOrderRepository
from app.services.strategy_state_repository import StrategyStateRepository
from app.services.strategy_signal_repository import StrategySignalRepository
from app.services.webhook_audit_repository import WebhookAuditRepository


class DashboardRepository:
    # This repository only reads from SQLite. It does not change webhook data,
    # trading logic, strategy rules, or AI analysis rows.
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_snapshot(self) -> DashboardSnapshot:
        trades = self.list_trades(limit=100)
        latest_trade = next((trade for trade in trades if trade.event_type == "ENTRY"), None)
        open_positions = self.list_positions("OPEN", 100)
        closed_positions = self.list_positions("CLOSED", 100)
        equity_curve = self._build_equity_curve(closed_positions)
        analysis_jobs = AnalysisJobRepository(self.database_path)

        return DashboardSnapshot(
            backend_status="reachable",
            current_symbol=latest_trade.ticker if latest_trade else "QQQ",
            current_session=self._session_label(),
            configuration_warnings=settings.runtime_warnings(),
            account=self._build_account_summary(trades, open_positions, closed_positions, equity_curve),
            latest_trade=latest_trade,
            trades=trades,
            open_positions=open_positions,
            closed_positions=closed_positions,
            equity_curve=equity_curve,
            webhook_deliveries=[
                WebhookDelivery(**delivery)
                for delivery in WebhookAuditRepository(self.database_path).list_recent(25)
            ],
            analysis_jobs=analysis_jobs.status_counts(),
            analysis_queue=AnalysisQueueSummary(**analysis_jobs.operational_summary()),
            bot_state=BotStateRepository(self.database_path).get(),
            strategy_state=StrategyStateRepository(self.database_path).get(),
            strategy_signals=StrategySignalRepository(self.database_path).list_recent(25),
            execution_orders=ExecutionOrderRepository(self.database_path).list_recent(25),
        )

    def list_positions(self, status: str, limit: int) -> list[DashboardPosition]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, ticker, side, status, quantity, entry_price, stop_loss,
                       take_profit, opened_at, exit_price, closed_at, realized_pnl,
                       close_reason, gross_pnl, entry_commission,
                       exit_commission, slippage_cost
                FROM paper_positions
                WHERE status = ?
                ORDER BY COALESCE(closed_at, opened_at) DESC, id DESC
                LIMIT ?;
                """,
                (status, limit),
            ).fetchall()
        return [DashboardPosition(**dict(row)) for row in rows]

    def list_trades(self, limit: int = 100) -> list[DashboardTrade]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    t.id,
                    t.ticker,
                    t.action,
                    t.price,
                    t.timestamp,
                    t.reason_codes,
                    t.vwap,
                    t.ema50,
                    t.ema200,
                    t.opening_range_high,
                    t.opening_range_low,
                    t.volume,
                    t.average_volume,
                    t.atr,
                    t.stop_loss,
                    t.take_profit,
                    t.event_type,
                    p.realized_pnl,
                    a.id AS analysis_id,
                    a.trade_grade,
                    a.confidence_score,
                    a.plain_english_explanation,
                    a.why_the_trade_qualified,
                    a.risk_factors,
                    a.watch_after_entry,
                    a.educational_summary,
                    a.created_at AS analysis_created_at
                FROM trades t
                LEFT JOIN paper_positions p
                    ON p.entry_trade_id = t.id OR p.exit_trade_id = t.id
                LEFT JOIN trade_ai_analyses a
                    ON a.id = (
                        SELECT latest.id
                        FROM trade_ai_analyses latest
                        WHERE latest.trade_id = t.id
                        ORDER BY latest.created_at DESC, latest.id DESC
                        LIMIT 1
                    )
                ORDER BY t.timestamp DESC, t.id DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_trade(dict(row)) for row in rows]

    def get_trade(self, trade_id: int) -> DashboardTrade | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    t.id,
                    t.ticker,
                    t.action,
                    t.price,
                    t.timestamp,
                    t.reason_codes,
                    t.vwap,
                    t.ema50,
                    t.ema200,
                    t.opening_range_high,
                    t.opening_range_low,
                    t.volume,
                    t.average_volume,
                    t.atr,
                    t.stop_loss,
                    t.take_profit,
                    t.event_type,
                    p.realized_pnl,
                    a.id AS analysis_id,
                    a.trade_grade,
                    a.confidence_score,
                    a.plain_english_explanation,
                    a.why_the_trade_qualified,
                    a.risk_factors,
                    a.watch_after_entry,
                    a.educational_summary,
                    a.created_at AS analysis_created_at
                FROM trades t
                LEFT JOIN paper_positions p
                    ON p.entry_trade_id = t.id OR p.exit_trade_id = t.id
                LEFT JOIN trade_ai_analyses a
                    ON a.id = (
                        SELECT latest.id
                        FROM trade_ai_analyses latest
                        WHERE latest.trade_id = t.id
                        ORDER BY latest.created_at DESC, latest.id DESC
                        LIMIT 1
                    )
                WHERE t.id = ?;
                """,
                (trade_id,),
            ).fetchone()

        return self._row_to_trade(dict(row)) if row else None

    def _row_to_trade(self, row: dict) -> DashboardTrade:
        analysis = None
        if row["analysis_id"] is not None:
            analysis = DashboardAnalysis(
                id=row["analysis_id"],
                trade_id=row["id"],
                trade_grade=row["trade_grade"],
                confidence_score=row["confidence_score"],
                plain_english_explanation=row["plain_english_explanation"],
                why_the_trade_qualified=row["why_the_trade_qualified"],
                risk_factors=row["risk_factors"],
                watch_after_entry=row["watch_after_entry"],
                educational_summary=row["educational_summary"],
                created_at=row["analysis_created_at"],
            )

        return DashboardTrade(
            id=row["id"],
            ticker=row["ticker"],
            action=row["action"],
            price=row["price"],
            timestamp=row["timestamp"],
            reason_codes=json.loads(row["reason_codes"]),
            vwap=row["vwap"],
            ema50=row["ema50"],
            ema200=row["ema200"],
            opening_range_high=row["opening_range_high"],
            opening_range_low=row["opening_range_low"],
            volume=row["volume"],
            average_volume=row["average_volume"],
            atr=row["atr"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            outcome=self._infer_outcome(row),
            event_type=row["event_type"],
            realized_pnl=row["realized_pnl"],
            analysis=analysis,
        )

    def _build_account_summary(
        self,
        trades: list[DashboardTrade],
        open_positions: list[DashboardPosition],
        closed_positions: list[DashboardPosition],
        equity_curve: list[EquityPoint],
    ) -> AccountSummary:
        today = datetime.now().date()
        trades_today = [
            trade
            for trade in trades
            if trade.timestamp.date() == today and trade.event_type == "ENTRY"
        ]
        winning_trades = sum(1 for position in closed_positions if (position.realized_pnl or 0) > 0)
        losing_trades = sum(1 for position in closed_positions if (position.realized_pnl or 0) < 0)
        completed_trades = winning_trades + losing_trades
        win_rate = round((winning_trades / completed_trades) * 100, 1) if completed_trades else 0.0
        reward_risks = [self._reward_risk(trade) for trade in trades]
        known_reward_risks = [value for value in reward_risks if value is not None]
        realized_pnl = sum(position.realized_pnl or 0 for position in closed_positions)
        gross_profit = sum(max(position.realized_pnl or 0, 0) for position in closed_positions)
        gross_loss = abs(sum(min(position.realized_pnl or 0, 0) for position in closed_positions))
        final_point = equity_curve[-1] if equity_curve else None
        max_drawdown_point = max(equity_curve, key=lambda point: point.drawdown, default=None)

        return AccountSummary(
            trades_today=len(trades_today),
            open_positions=len(open_positions),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            average_reward_risk=round(sum(known_reward_risks) / len(known_reward_risks), 2)
            if known_reward_risks
            else None,
            realized_pnl=round(realized_pnl, 2),
            profit_factor=round(gross_profit / gross_loss, 2) if gross_loss else None,
            current_equity=final_point.equity if final_point else settings.paper_starting_cash,
            max_drawdown=max_drawdown_point.drawdown if max_drawdown_point else 0,
            max_drawdown_percent=max_drawdown_point.drawdown_percent if max_drawdown_point else 0,
        )

    def _build_equity_curve(self, closed_positions: list[DashboardPosition]) -> list[EquityPoint]:
        equity = settings.paper_starting_cash
        peak = equity
        points: list[EquityPoint] = []
        for position in sorted(closed_positions, key=lambda item: item.closed_at or item.opened_at):
            equity += position.realized_pnl or 0
            peak = max(peak, equity)
            drawdown = peak - equity
            points.append(
                EquityPoint(
                    timestamp=position.closed_at or position.opened_at,
                    equity=round(equity, 2),
                    cumulative_pnl=round(equity - settings.paper_starting_cash, 2),
                    drawdown=round(drawdown, 2),
                    drawdown_percent=round(drawdown / peak * 100, 2) if peak else 0,
                )
            )
        return points

    def _reward_risk(self, trade: DashboardTrade) -> float | None:
        if trade.stop_loss is None or trade.take_profit is None:
            return None

        risk = abs(trade.price - trade.stop_loss)
        reward = abs(trade.take_profit - trade.price)
        return reward / risk if risk else None

    def _infer_outcome(self, row: dict) -> str | None:
        if row["realized_pnl"] is None:
            return None
        if row["realized_pnl"] > 0:
            return "WIN"
        if row["realized_pnl"] < 0:
            return "LOSS"
        return "BREAKEVEN"

    def _session_label(self) -> str:
        now = datetime.now().time()
        if now.hour == 9 and now.minute >= 30 or now.hour == 10 or now.hour == 11 and now.minute <= 30:
            return "Morning QQQ Session"
        return "Outside Trading Window"
