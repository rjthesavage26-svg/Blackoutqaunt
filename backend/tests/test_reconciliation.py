from pathlib import Path

from app.brokers.base import BrokerPosition
from app.db.sqlite import connect, initialize_database
from app.services.reconciliation import reconcile_positions


class FakeBroker:
    def __init__(self, positions: list[BrokerPosition]) -> None:
        self._positions = positions

    def submit_order(self, order):  # pragma: no cover - not needed for reconciliation tests
        raise AssertionError("Reconciliation must not submit broker orders.")

    def list_positions(self) -> list[BrokerPosition]:
        return self._positions


def seed_open_position(
    database_path: Path,
    *,
    ticker: str = "QQQ",
    side: str = "LONG",
    quantity: float = 2.0,
    entry_price: float = 100.0,
) -> None:
    initialize_database(database_path)
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO trades (
                ticker, action, price, timestamp, reason_codes, raw_payload, event_type
            ) VALUES (?, ?, ?, ?, ?, ?, 'ENTRY');
            """,
            (
                ticker,
                "BUY" if side == "LONG" else "SELL",
                entry_price,
                "2026-08-06T10:00:00-04:00",
                '["TEST"]',
                "{}",
            ),
        )
        trade_id = connection.execute("SELECT last_insert_rowid();").fetchone()[0]
        connection.execute(
            """
            INSERT INTO paper_positions (
                entry_trade_id, ticker, side, status, quantity, entry_price, opened_at
            ) VALUES (?, ?, ?, 'OPEN', ?, ?, ?);
            """,
            (trade_id, ticker, side, quantity, entry_price, "2026-08-06T10:00:00-04:00"),
        )


def test_reconciliation_reports_no_differences_when_position_matches(tmp_path: Path) -> None:
    database_path = tmp_path / "matching.db"
    seed_open_position(database_path, quantity=2.0, entry_price=100.0)

    differences = reconcile_positions(
        database_path,
        FakeBroker([BrokerPosition(ticker="QQQ", side="LONG", quantity=2.0, average_price=100.0)]),
    )

    assert differences == []


def test_reconciliation_detects_local_only_broker_only_side_quantity_and_price_mismatches(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "mismatches.db"
    seed_open_position(database_path, ticker="QQQ", side="LONG", quantity=2.0, entry_price=100.0)
    seed_open_position(database_path, ticker="SPY", side="SHORT", quantity=1.0, entry_price=500.0)

    differences = reconcile_positions(
        database_path,
        FakeBroker(
            [
                BrokerPosition(ticker="QQQ", side="LONG", quantity=2.5, average_price=101.0),
                BrokerPosition(ticker="IWM", side="LONG", quantity=3.0, average_price=250.0),
                BrokerPosition(ticker="SPY", side="LONG", quantity=1.0, average_price=500.0),
            ]
        ),
    )

    assert [difference.ticker for difference in differences] == ["IWM", "QQQ", "SPY"]
    iwm, qqq, spy = differences
    assert iwm.local_side is None
    assert iwm.broker_side == "LONG"
    assert iwm.local_quantity == 0.0
    assert iwm.broker_quantity == 3.0
    assert iwm.local_average_price is None
    assert iwm.broker_average_price == 250.0

    assert qqq.local_side == "LONG"
    assert qqq.broker_side == "LONG"
    assert qqq.local_quantity == 2.0
    assert qqq.broker_quantity == 2.5
    assert qqq.local_average_price == 100.0
    assert qqq.broker_average_price == 101.0

    assert spy.local_side == "SHORT"
    assert spy.broker_side == "LONG"
    assert spy.local_quantity == 1.0
    assert spy.broker_quantity == 1.0
    assert spy.local_average_price == 500.0
    assert spy.broker_average_price == 500.0
