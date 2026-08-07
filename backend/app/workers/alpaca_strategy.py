from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.db.sqlite import connect, initialize_database
from app.models.tradingview import TradingViewAlert
from app.services.alpaca_market_data import AlpacaMarketDataClient
from app.services.analysis_job_repository import AnalysisJobRepository
from app.services.bot_state_repository import BotStateRepository
from app.services.strategy_signal_repository import StrategySignalRepository
from app.services.strategy_state_repository import StrategyStateRepository
from app.services.trade_repository import TradeRepository
from app.brokers.factory import get_execution_service
from app.strategy.multi_strategy import MultiStrategyEngine
from app.strategy.qqq_orb import NY, StrategyDecision

LOGGER = logging.getLogger(__name__)


def has_open_position() -> bool:
    with connect(settings.database_path) as connection:
        row = connection.execute(
            "SELECT id FROM paper_positions WHERE ticker = ? AND status = 'OPEN' LIMIT 1;",
            (settings.strategy_symbol.upper(),),
        ).fetchone()
    return row is not None


def latest_entry_event_id() -> str | None:
    with connect(settings.database_path) as connection:
        row = connection.execute(
            """
            SELECT event_id FROM trades
            WHERE event_id LIKE ? AND event_type = 'ENTRY'
            ORDER BY id DESC LIMIT 1;
            """,
            (f"alpaca-{settings.strategy_symbol.upper()}-%",),
        ).fetchone()
    return row["event_id"] if row else None


def event_exists(event_id: str) -> bool:
    with connect(settings.database_path) as connection:
        row = connection.execute("SELECT id FROM trades WHERE event_id = ?;", (event_id,)).fetchone()
    return row is not None


def run_once(now: datetime | None = None) -> bool:
    initialize_database(settings.database_path)
    state = StrategyStateRepository(settings.database_path)
    bot = BotStateRepository(settings.database_path)

    if not bot.is_running():
        state.update(status="STOPPED", message="Bot is stopped; strategy did not poll Alpaca.")
        return False
    if not settings.alpaca_api_key or not settings.alpaca_api_secret:
        state.update(status="ERROR", message="Alpaca API credentials are not configured.")
        return False

    current_time = now or datetime.now(UTC)
    start = current_time - timedelta(days=10)
    client = AlpacaMarketDataClient(
        base_url=settings.alpaca_data_base_url,
        api_key=settings.alpaca_api_key,
        api_secret=settings.alpaca_api_secret,
        feed=settings.alpaca_data_feed,
    )
    bars = client.get_stock_bars(
        symbol=settings.strategy_symbol.upper(),
        start=start,
        end=current_time,
        timeframe="5Min",
        limit=1000,
    )
    if not bars:
        state.update(status="NO_DATA", message="Alpaca returned no market bars.")
        return False

    engine = MultiStrategyEngine()
    open_position = has_open_position()
    candidates, baseline = engine.scan(bars, has_open_position=open_position)
    latest_bar = bars[-1]
    session_date = latest_bar.timestamp.astimezone(NY).date().isoformat()
    decision = candidates[0] if candidates else baseline
    latest_signal = decision.action if decision.should_enter else None
    state.update(
        status="SIGNAL" if candidates else "WATCHING",
        message=decision.message if candidates else f"No strategy setup qualified. {baseline.message}",
        session_date=session_date,
        last_bar_at=latest_bar.timestamp.isoformat(),
        opening_range_high=decision.opening_range_high,
        opening_range_low=decision.opening_range_low,
        latest_signal=latest_signal,
    )

    if not candidates:
        return False

    selected = candidates[0]
    event_id = _event_id(latest_bar.timestamp, selected)
    signals = StrategySignalRepository(settings.database_path)
    for candidate in candidates:
        candidate_event_id = _event_id(latest_bar.timestamp, candidate)
        status = "SELECTED" if candidate is selected else "REJECTED"
        reason = "highest_score" if candidate is selected else f"lower_score_than_{selected.strategy_name}"
        signals.record(decision=candidate, event_id=candidate_event_id, status=status, reason=reason)

    if event_exists(event_id):
        state.update(status="DUPLICATE", message=f"Signal {event_id} already processed.")
        return False

    alert = TradingViewAlert(
        ticker=settings.strategy_symbol.upper(),
        action=selected.action,
        price=selected.price,
        time=latest_bar.timestamp,
        reason_codes=selected.reason_codes,
        vwap=selected.vwap,
        ema50=selected.ema50,
        ema200=selected.ema200,
        opening_range_high=selected.opening_range_high,
        opening_range_low=selected.opening_range_low,
        volume=selected.volume,
        average_volume=selected.average_volume,
        atr=selected.atr,
        stop_loss=selected.stop_loss,
        take_profit=selected.take_profit,
        event_type="ENTRY",
        event_id=event_id,
    )
    raw_payload = alert.model_dump(mode="json")
    raw_payload["source"] = "alpaca_strategy_worker"
    raw_payload["strategy_name"] = selected.strategy_name
    raw_payload["strategy_score"] = selected.score
    trade = TradeRepository(settings.database_path).save_tradingview_alert(alert=alert, raw_payload=raw_payload)
    get_execution_service().process_alert(alert, trade)
    AnalysisJobRepository(settings.database_path).enqueue(trade.id)
    state.update(
        status="ORDER_SUBMITTED",
        message=f"Processed standalone strategy signal {event_id}.",
        session_date=session_date,
        last_bar_at=latest_bar.timestamp.isoformat(),
        opening_range_high=selected.opening_range_high,
        opening_range_low=selected.opening_range_low,
        latest_signal=f"{selected.strategy_name}:{selected.action}",
    )
    LOGGER.info("alpaca_strategy_signal_processed", extra={"trade_id": trade.id, "ticker": alert.ticker})
    return True


def _event_id(timestamp: datetime, decision: StrategyDecision) -> str:
    return (
        f"alpaca-{settings.strategy_symbol.upper()}-{int(timestamp.timestamp())}-"
        f"{decision.strategy_name}-ENTRY-{decision.action}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the standalone Alpaca QQQ ORB strategy worker.")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle and exit.")
    args = parser.parse_args()
    logging.basicConfig(level=settings.log_level)

    if args.once:
        run_once()
        return

    while True:
        try:
            run_once()
        except Exception as error:  # pragma: no cover - defensive long-running worker guard
            LOGGER.exception("alpaca_strategy_worker_error")
            StrategyStateRepository(settings.database_path).update(status="ERROR", message=str(error))
        time.sleep(settings.strategy_poll_seconds)


if __name__ == "__main__":
    main()
