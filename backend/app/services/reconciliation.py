from dataclasses import dataclass
from pathlib import Path

from app.brokers.base import BrokerAdapter
from app.db.sqlite import connect


@dataclass(frozen=True)
class ReconciliationDifference:
    ticker: str
    local_side: str | None
    broker_side: str | None
    local_quantity: float
    broker_quantity: float
    local_average_price: float | None
    broker_average_price: float | None


def reconcile_positions(database_path: Path, broker: BrokerAdapter) -> list[ReconciliationDifference]:
    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT ticker, side, quantity, entry_price
            FROM paper_positions
            WHERE status = 'OPEN';
            """
        ).fetchall()
    local = {
        row["ticker"]: (row["side"], row["quantity"], row["entry_price"])
        for row in rows
    }
    remote = {
        position.ticker: (position.side, position.quantity, position.average_price)
        for position in broker.list_positions()
    }
    differences: list[ReconciliationDifference] = []
    for ticker in sorted(set(local) | set(remote)):
        local_side, local_quantity, local_average_price = local.get(ticker, (None, 0.0, None))
        broker_side, broker_quantity, broker_average_price = remote.get(ticker, (None, 0.0, None))
        prices_match = (
            local_average_price is None
            and broker_average_price is None
        ) or (
            local_average_price is not None
            and broker_average_price is not None
            and abs(local_average_price - broker_average_price) <= 1e-6
        )
        if (
            local_side != broker_side
            or abs(local_quantity - broker_quantity) > 1e-8
            or not prices_match
        ):
            differences.append(
                ReconciliationDifference(
                    ticker=ticker,
                    local_side=local_side,
                    broker_side=broker_side,
                    local_quantity=local_quantity,
                    broker_quantity=broker_quantity,
                    local_average_price=local_average_price,
                    broker_average_price=broker_average_price,
                )
            )
    return differences
