from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class MarketBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class StrategyDecision:
    should_enter: bool
    action: str | None
    reason_codes: list[str]
    price: float | None
    stop_loss: float | None
    take_profit: float | None
    vwap: float | None
    ema50: float | None
    ema200: float | None
    opening_range_high: float | None
    opening_range_low: float | None
    volume: float | None
    average_volume: float | None
    atr: float | None
    message: str
    strategy_name: str = "QQQ_ORB"
    score: int = 0


class QqqOrbStrategy:
    """Python implementation of the Pine QQQ ORB strategy.

    The evaluator is deterministic and side-effect free. It expects 5-minute QQQ
    bars ordered oldest to newest and returns a single latest-bar decision.
    """

    def __init__(
        self,
        *,
        atr_length: int = 14,
        atr_stop_multiplier: float = 1.5,
        reward_risk_ratio: float = 2.0,
        volume_average_length: int = 20,
        volume_multiplier: float = 1.5,
    ) -> None:
        self.atr_length = atr_length
        self.atr_stop_multiplier = atr_stop_multiplier
        self.reward_risk_ratio = reward_risk_ratio
        self.volume_average_length = volume_average_length
        self.volume_multiplier = volume_multiplier

    def evaluate(self, bars: list[MarketBar], *, has_open_position: bool) -> StrategyDecision:
        if len(bars) < 200:
            return self._no_trade("Need at least 200 bars for EMA 200.", bars)

        ordered = sorted(bars, key=lambda item: item.timestamp)
        latest = ordered[-1]
        latest_time = latest.timestamp.astimezone(NY)
        session_date = latest_time.date()
        session_bars = [bar for bar in ordered if bar.timestamp.astimezone(NY).date() == session_date]

        opening_bars = [
            bar for bar in session_bars
            if time(9, 30) <= bar.timestamp.astimezone(NY).time() < time(9, 45)
        ]
        if not opening_bars:
            return self._no_trade("Opening range is not ready.", ordered)

        opening_range_high = max(bar.high for bar in opening_bars)
        opening_range_low = min(bar.low for bar in opening_bars)

        if latest_time.time() < time(9, 45):
            return self._no_trade("Still building opening range.", ordered, opening_range_high, opening_range_low)
        if latest_time.time() >= time(16, 0):
            return self._no_trade("Outside regular market hours.", ordered, opening_range_high, opening_range_low)
        if has_open_position:
            return self._no_trade("Existing open position blocks new entries.", ordered, opening_range_high, opening_range_low)

        closes = [bar.close for bar in ordered]
        ema50 = self._ema(closes, 50)
        ema200 = self._ema(closes, 200)
        atr = self._atr(ordered, self.atr_length)
        average_volume = self._sma([bar.volume for bar in ordered], self.volume_average_length)
        vwap = self._session_vwap(session_bars)

        if None in {ema50, ema200, atr, average_volume, vwap}:
            return self._no_trade("Indicator warmup is incomplete.", ordered, opening_range_high, opening_range_low)

        volume_is_valid = latest.volume >= self.volume_multiplier * average_volume
        long_valid = (
            latest.close > vwap
            and ema50 > ema200
            and latest.close > opening_range_high
            and volume_is_valid
        )
        short_valid = (
            latest.close < vwap
            and ema50 < ema200
            and latest.close < opening_range_low
            and volume_is_valid
        )

        if long_valid:
            stop_loss = latest.close - (atr * self.atr_stop_multiplier)
            risk = latest.close - stop_loss
            take_profit = latest.close + (risk * self.reward_risk_ratio)
            return StrategyDecision(
                should_enter=True,
                action="BUY",
                reason_codes=["VWAP_LONG", "EMA_BULLISH", "ORB_BREAKOUT", "HIGH_VOLUME"],
                price=latest.close,
                stop_loss=round(stop_loss, 4),
                take_profit=round(take_profit, 4),
                vwap=round(vwap, 4),
                ema50=round(ema50, 4),
                ema200=round(ema200, 4),
                opening_range_high=round(opening_range_high, 4),
                opening_range_low=round(opening_range_low, 4),
                volume=latest.volume,
                average_volume=round(average_volume, 4),
                atr=round(atr, 4),
                message="Long QQQ ORB setup qualified.",
                score=90,
            )

        if short_valid:
            stop_loss = latest.close + (atr * self.atr_stop_multiplier)
            risk = stop_loss - latest.close
            take_profit = latest.close - (risk * self.reward_risk_ratio)
            return StrategyDecision(
                should_enter=True,
                action="SELL",
                reason_codes=["VWAP_SHORT", "EMA_BEARISH", "ORB_BREAKDOWN", "HIGH_VOLUME"],
                price=latest.close,
                stop_loss=round(stop_loss, 4),
                take_profit=round(take_profit, 4),
                vwap=round(vwap, 4),
                ema50=round(ema50, 4),
                ema200=round(ema200, 4),
                opening_range_high=round(opening_range_high, 4),
                opening_range_low=round(opening_range_low, 4),
                volume=latest.volume,
                average_volume=round(average_volume, 4),
                atr=round(atr, 4),
                message="Short QQQ ORB setup qualified.",
                score=90,
            )

        return StrategyDecision(
            should_enter=False,
            action=None,
            reason_codes=[],
            price=latest.close,
            stop_loss=None,
            take_profit=None,
            vwap=round(vwap, 4),
            ema50=round(ema50, 4),
            ema200=round(ema200, 4),
            opening_range_high=round(opening_range_high, 4),
            opening_range_low=round(opening_range_low, 4),
            volume=latest.volume,
            average_volume=round(average_volume, 4),
            atr=round(atr, 4),
            message="No QQQ ORB setup qualified on the latest bar.",
        )

    def _no_trade(
        self,
        message: str,
        bars: list[MarketBar],
        opening_range_high: float | None = None,
        opening_range_low: float | None = None,
    ) -> StrategyDecision:
        latest = bars[-1] if bars else None
        return StrategyDecision(
            should_enter=False,
            action=None,
            reason_codes=[],
            price=latest.close if latest else None,
            stop_loss=None,
            take_profit=None,
            vwap=None,
            ema50=None,
            ema200=None,
            opening_range_high=opening_range_high,
            opening_range_low=opening_range_low,
            volume=latest.volume if latest else None,
            average_volume=None,
            atr=None,
            message=message,
        )

    def _ema(self, values: list[float], length: int) -> float | None:
        if len(values) < length:
            return None
        multiplier = 2 / (length + 1)
        ema = sum(values[:length]) / length
        for value in values[length:]:
            ema = (value - ema) * multiplier + ema
        return ema

    def _sma(self, values: list[float], length: int) -> float | None:
        if len(values) < length:
            return None
        return sum(values[-length:]) / length

    def _atr(self, bars: list[MarketBar], length: int) -> float | None:
        if len(bars) <= length:
            return None
        true_ranges: list[float] = []
        for index in range(1, len(bars)):
            current = bars[index]
            previous = bars[index - 1]
            true_ranges.append(
                max(
                    current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close),
                )
            )
        return self._sma(true_ranges, length)

    def _session_vwap(self, bars: list[MarketBar]) -> float | None:
        total_volume = sum(bar.volume for bar in bars)
        if total_volume <= 0:
            return None
        weighted = sum(((bar.high + bar.low + bar.close) / 3) * bar.volume for bar in bars)
        return weighted / total_volume
