from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class BrokerOrder:
    client_order_id: str
    ticker: str
    side: str
    quantity: float
    reference_price: float
    submitted_at: datetime
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class BrokerFill:
    broker_order_id: str
    client_order_id: str
    ticker: str
    side: str
    quantity: float
    fill_price: float
    commission: float
    filled_at: datetime


@dataclass(frozen=True)
class BrokerPosition:
    ticker: str
    side: str
    quantity: float
    average_price: float


class BrokerAdapter(Protocol):
    """Execution contract. Implementations must be idempotent by client_order_id."""

    def submit_order(self, order: BrokerOrder) -> BrokerFill: ...

    def list_positions(self) -> list[BrokerPosition]: ...
