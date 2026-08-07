from __future__ import annotations

import logging
from pathlib import Path

from app.db.sqlite import connect
from app.models.tradingview import SavedTrade, TradingViewAlert

LOGGER = logging.getLogger(__name__)


class PaperBroker:
    """Persist deterministic paper fills behind a broker-shaped boundary."""

    def __init__(
        self,
        database_path: Path,
        default_notional: float,
        slippage_bps: float = 0,
        commission_per_order: float = 0,
    ) -> None:
        self.database_path = database_path
        self.default_notional = default_notional
        self.slippage_bps = slippage_bps
        self.commission_per_order = commission_per_order

    def process_alert(self, alert: TradingViewAlert, trade: SavedTrade) -> None:
        if alert.event_type == "ENTRY":
            self._open_position(alert, trade)
        else:
            self._close_position(alert, trade)

    def _open_position(self, alert: TradingViewAlert, trade: SavedTrade) -> None:
        side = "LONG" if alert.action == "BUY" else "SHORT"
        quantity = alert.quantity or self.default_notional / alert.price
        fill_price = self._fill_price(alert.price, alert.action)
        slippage_cost = abs(fill_price - alert.price) * quantity

        with connect(self.database_path) as connection:
            existing = connection.execute(
                "SELECT id FROM paper_positions WHERE ticker = ? AND status = 'OPEN';",
                (alert.ticker,),
            ).fetchone()
            if existing:
                LOGGER.warning(
                    "paper_position_entry_ignored",
                    extra={"ticker": alert.ticker, "reason": "position_already_open"},
                )
                return

            connection.execute(
                """
                INSERT INTO paper_positions (
                    entry_trade_id, ticker, side, status, quantity, entry_price,
                    stop_loss, take_profit, opened_at, entry_commission, slippage_cost
                ) VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    trade.id,
                    alert.ticker,
                    side,
                    quantity,
                    fill_price,
                    alert.stop_loss,
                    alert.take_profit,
                    alert.timestamp.isoformat(),
                    self.commission_per_order,
                    slippage_cost,
                ),
            )
        LOGGER.info("paper_position_opened", extra={"trade_id": trade.id, "side": side})

    def _close_position(self, alert: TradingViewAlert, trade: SavedTrade) -> None:
        with connect(self.database_path) as connection:
            position = connection.execute(
                """
                SELECT * FROM paper_positions
                WHERE ticker = ? AND status = 'OPEN'
                ORDER BY opened_at DESC, id DESC LIMIT 1;
                """,
                (alert.ticker,),
            ).fetchone()
            if position is None:
                LOGGER.warning(
                    "paper_position_exit_ignored",
                    extra={"ticker": alert.ticker, "reason": "no_open_position"},
                )
                return

            direction = 1 if position["side"] == "LONG" else -1
            exit_action = "SELL" if position["side"] == "LONG" else "BUY"
            exit_fill_price = self._fill_price(alert.price, exit_action)
            exit_slippage = abs(exit_fill_price - alert.price) * position["quantity"]
            gross_pnl = (exit_fill_price - position["entry_price"]) * position["quantity"] * direction
            realized_pnl = gross_pnl - position["entry_commission"] - self.commission_per_order
            connection.execute(
                """
                UPDATE paper_positions
                SET status = 'CLOSED', exit_trade_id = ?, exit_price = ?,
                    closed_at = ?, realized_pnl = ?, gross_pnl = ?,
                    exit_commission = ?, slippage_cost = slippage_cost + ?, close_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    trade.id,
                    exit_fill_price,
                    alert.timestamp.isoformat(),
                    realized_pnl,
                    gross_pnl,
                    self.commission_per_order,
                    exit_slippage,
                    "TRADINGVIEW_EXIT",
                    position["id"],
                ),
            )
        LOGGER.info(
            "paper_position_closed",
            extra={"trade_id": trade.id, "position_id": position["id"], "realized_pnl": realized_pnl},
        )

    def _fill_price(self, reference_price: float, action: str) -> float:
        direction = 1 if action == "BUY" else -1
        return reference_price * (1 + direction * self.slippage_bps / 10_000)
