from datetime import datetime, timedelta

from app.brokers.alpaca import AlpacaPaperBroker
from app.brokers.base import BrokerOrder
from app.strategy.multi_strategy import MultiStrategyEngine
from app.strategy.qqq_orb import MarketBar, NY, QqqOrbStrategy


def build_warm_bars() -> list[MarketBar]:
    start = datetime(2026, 8, 5, 9, 30, tzinfo=NY)
    bars: list[MarketBar] = []
    for index in range(210):
        price = 90 + index * 0.1
        bars.append(
            MarketBar(
                timestamp=start + timedelta(minutes=5 * index),
                open=price,
                high=price + 0.4,
                low=price - 0.4,
                close=price + 0.2,
                volume=1000,
            )
        )
    return bars


def test_qqq_orb_strategy_generates_long_signal() -> None:
    bars = build_warm_bars()
    session_date = datetime(2026, 8, 7, tzinfo=NY)
    bars.extend(
        [
            MarketBar(session_date.replace(hour=9, minute=30), 112, 113, 111, 112, 1000),
            MarketBar(session_date.replace(hour=9, minute=35), 112, 113.2, 111.5, 112.5, 1000),
            MarketBar(session_date.replace(hour=9, minute=40), 112.5, 113.5, 112, 113, 1000),
            MarketBar(session_date.replace(hour=9, minute=45), 113.2, 116, 113, 115.5, 10000),
        ]
    )

    decision = QqqOrbStrategy().evaluate(bars, has_open_position=False)

    assert decision.should_enter is True
    assert decision.action == "BUY"
    assert decision.reason_codes == ["VWAP_LONG", "EMA_BULLISH", "ORB_BREAKOUT", "HIGH_VOLUME"]
    assert decision.opening_range_high == 113.5
    assert decision.stop_loss is not None
    assert decision.take_profit is not None
    assert decision.take_profit > decision.price > decision.stop_loss


def test_qqq_orb_strategy_blocks_when_position_is_open() -> None:
    bars = build_warm_bars()

    decision = QqqOrbStrategy().evaluate(bars, has_open_position=True)

    assert decision.should_enter is False


def test_qqq_orb_strategy_can_trade_after_morning_window() -> None:
    bars = build_warm_bars()
    session_date = datetime(2026, 8, 7, tzinfo=NY)
    bars.extend(
        [
            MarketBar(session_date.replace(hour=9, minute=30), 112, 113, 111, 112, 1000),
            MarketBar(session_date.replace(hour=9, minute=35), 112, 113.2, 111.5, 112.5, 1000),
            MarketBar(session_date.replace(hour=9, minute=40), 112.5, 113.5, 112, 113, 1000),
            MarketBar(session_date.replace(hour=13, minute=35), 113.2, 116, 113, 115.5, 10000),
        ]
    )

    decision = QqqOrbStrategy().evaluate(bars, has_open_position=False)

    assert decision.should_enter is True
    assert decision.action == "BUY"


def test_alpaca_bracket_payload_is_paper_order_shape() -> None:
    broker = AlpacaPaperBroker(
        base_url="https://paper-api.alpaca.markets",
        api_key="paper-key",
        api_secret="paper-secret",
    )
    order = BrokerOrder(
        client_order_id="test-order",
        ticker="QQQ",
        side="BUY",
        quantity=1,
        reference_price=115,
        submitted_at=datetime(2026, 8, 7, tzinfo=NY),
        stop_loss=113,
        take_profit=119,
    )

    payload = broker.order_payload(order)

    assert payload["order_class"] == "bracket"
    assert payload["take_profit"]["limit_price"] == "119"
    assert payload["stop_loss"]["stop_price"] == "113"


def test_multi_strategy_engine_ranks_candidates() -> None:
    bars = build_warm_bars()
    session_date = datetime(2026, 8, 7, tzinfo=NY)
    bars.extend(
        [
            MarketBar(session_date.replace(hour=9, minute=30), 112, 113, 111, 112, 1000),
            MarketBar(session_date.replace(hour=9, minute=35), 112, 113.2, 111.5, 112.5, 1000),
            MarketBar(session_date.replace(hour=9, minute=40), 112.5, 113.5, 112, 113, 1000),
            MarketBar(session_date.replace(hour=13, minute=35), 113.2, 116, 113, 115.5, 10000),
        ]
    )

    candidates, baseline = MultiStrategyEngine().scan(bars, has_open_position=False)

    assert candidates
    assert candidates[0].score >= candidates[-1].score
    assert candidates[0].strategy_name == "QQQ_ORB"
    assert baseline.strategy_name == "QQQ_ORB"
