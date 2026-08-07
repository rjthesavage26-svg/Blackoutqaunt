from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.brokers.base import BrokerFill, BrokerOrder, BrokerPosition


class AlpacaPaperBroker:
    """Alpaca Paper Trading adapter.

    This adapter intentionally accepts only Alpaca's paper API base URL. It must
    not be pointed at the live trading endpoint.
    """

    def __init__(self, *, base_url: str, api_key: str, api_secret: str, timeout_seconds: float = 10) -> None:
        if "paper-api.alpaca.markets" not in base_url:
            raise ValueError("AlpacaPaperBroker only supports the Alpaca paper trading endpoint.")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout_seconds = timeout_seconds

    def submit_order(self, order: BrokerOrder) -> BrokerFill:
        payload: dict[str, Any] = {
            "symbol": order.ticker,
            "qty": str(order.quantity),
            "side": order.side.lower(),
            "type": "market",
            "time_in_force": "day",
            "client_order_id": order.client_order_id,
        }
        if order.stop_loss and order.take_profit:
            payload["order_class"] = "bracket"
            payload["take_profit"] = {"limit_price": str(round(order.take_profit, 2))}
            payload["stop_loss"] = {"stop_price": str(round(order.stop_loss, 2))}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/v2/orders",
                headers=self._headers(),
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        submitted_at = self._parse_time(data.get("submitted_at")) or order.submitted_at
        return BrokerFill(
            broker_order_id=str(data.get("id", "")),
            client_order_id=order.client_order_id,
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            fill_price=float(data.get("filled_avg_price") or order.reference_price),
            commission=0,
            filled_at=submitted_at,
        )

    def list_positions(self) -> list[BrokerPosition]:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(f"{self.base_url}/v2/positions", headers=self._headers())
        response.raise_for_status()
        positions = []
        for item in response.json():
            quantity = float(item["qty"])
            positions.append(
                BrokerPosition(
                    ticker=item["symbol"],
                    side="LONG" if quantity >= 0 else "SHORT",
                    quantity=abs(quantity),
                    average_price=float(item["avg_entry_price"]),
                )
            )
        return positions

    def order_payload(self, order: BrokerOrder) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": order.ticker,
            "qty": str(order.quantity),
            "side": order.side.lower(),
            "type": "market",
            "time_in_force": "day",
            "client_order_id": order.client_order_id,
        }
        if order.stop_loss and order.take_profit:
            payload["order_class"] = "bracket"
            payload["take_profit"] = {"limit_price": str(round(order.take_profit, 2))}
            payload["stop_loss"] = {"stop_price": str(round(order.stop_loss, 2))}
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
        }

    def _parse_time(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
