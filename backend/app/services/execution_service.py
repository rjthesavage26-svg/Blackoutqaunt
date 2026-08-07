from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from app.brokers.alpaca import AlpacaPaperBroker
from app.brokers.base import BrokerOrder
from app.core.config import settings
from app.models.tradingview import SavedTrade, TradingViewAlert
from app.services.execution_order_repository import ExecutionOrderRepository
from app.services.bot_state_repository import BotStateRepository
from app.services.paper_broker import PaperBroker

LOGGER = logging.getLogger(__name__)


class TradingExecutionService:
    """Coordinates local ledger updates and optional real paper broker orders."""

    def __init__(self) -> None:
        self.local_paper = PaperBroker(
            settings.database_path,
            settings.paper_position_notional,
            settings.paper_slippage_bps,
            settings.paper_commission_per_order,
        )
        self.execution_orders = ExecutionOrderRepository(settings.database_path)

    def process_alert(self, alert: TradingViewAlert, trade: SavedTrade) -> None:
        self.local_paper.process_alert(alert, trade)
        if settings.execution_mode == "internal_paper":
            return
        if not BotStateRepository(settings.database_path).is_running():
            LOGGER.warning(
                "external_execution_skipped",
                extra={"trade_id": trade.id, "reason": "bot_not_running"},
            )
            return
        if settings.execution_mode == "alpaca_paper":
            self._submit_alpaca_paper_order(alert, trade)
            return
        raise RuntimeError(f"Unsupported execution mode: {settings.execution_mode}")

    def _submit_alpaca_paper_order(self, alert: TradingViewAlert, trade: SavedTrade) -> None:
        if not settings.alpaca_api_key or not settings.alpaca_api_secret:
            raise RuntimeError("Alpaca paper execution requires ALPACA_API_KEY and ALPACA_API_SECRET.")

        quantity = alert.quantity or max(settings.paper_position_notional / alert.price, 0)
        client_order_id = alert.event_id or f"blackout-quant-{trade.id}"
        order = BrokerOrder(
            client_order_id=client_order_id,
            ticker=alert.ticker,
            side=alert.action,
            quantity=round(quantity, 6),
            reference_price=alert.price,
            submitted_at=datetime.now(UTC),
            stop_loss=alert.stop_loss if alert.event_type == "ENTRY" else None,
            take_profit=alert.take_profit if alert.event_type == "ENTRY" else None,
        )
        broker = AlpacaPaperBroker(
            base_url=settings.alpaca_paper_base_url,
            api_key=settings.alpaca_api_key,
            api_secret=settings.alpaca_api_secret,
        )
        self.execution_orders.create_submitted(
            trade_id=trade.id,
            client_order_id=client_order_id,
            execution_mode=settings.execution_mode,
            broker="alpaca",
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            submitted_payload=broker.order_payload(order),
        )
        try:
            fill = broker.submit_order(order)
        except httpx.HTTPStatusError as error:
            message = f"Alpaca rejected order with HTTP {error.response.status_code}: {error.response.text[:500]}"
            self.execution_orders.mark_rejected(client_order_id=client_order_id, error_message=message)
            LOGGER.error("alpaca_paper_order_rejected", extra={"trade_id": trade.id, "reason": message})
            raise RuntimeError(message) from error
        except Exception as error:
            message = str(error)
            self.execution_orders.mark_rejected(client_order_id=client_order_id, error_message=message)
            LOGGER.error("alpaca_paper_order_failed", extra={"trade_id": trade.id, "reason": message})
            raise

        self.execution_orders.mark_accepted(
            client_order_id=client_order_id,
            broker_order_id=fill.broker_order_id,
            response_payload=fill.__dict__,
            status="ACCEPTED",
        )
        LOGGER.info(
            "alpaca_paper_order_accepted",
            extra={"trade_id": trade.id, "ticker": alert.ticker, "event_type": alert.event_type},
        )
