from __future__ import annotations

from dataclasses import replace
from datetime import time

from app.strategy.qqq_orb import MarketBar, NY, QqqOrbStrategy, StrategyDecision


class MultiStrategyEngine:
    """Evaluate all enabled QQQ strategies and rank executable candidates."""

    def __init__(self) -> None:
        self.base = QqqOrbStrategy()

    def scan(self, bars: list[MarketBar], *, has_open_position: bool) -> tuple[list[StrategyDecision], StrategyDecision]:
        ordered = sorted(bars, key=lambda item: item.timestamp)
        baseline = self.base.evaluate(ordered, has_open_position=has_open_position)
        if has_open_position:
            return [], baseline

        candidates: list[StrategyDecision] = []
        if baseline.should_enter:
            candidates.append(baseline)

        for decision in (self._vwap_reclaim_or_reject(ordered), self._ema_trend_pullback(ordered)):
            if decision.should_enter:
                candidates.append(decision)

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates, baseline

    def _vwap_reclaim_or_reject(self, bars: list[MarketBar]) -> StrategyDecision:
        context = self._context(bars)
        if context is None:
            return self.base._no_trade("VWAP strategy indicator warmup incomplete.", bars)
        latest, previous, session_bars, vwap, ema50, ema200, atr, average_volume = context
        if not self._is_trade_time(latest):
            return self.base._no_trade("Outside regular market hours.", bars)

        volume_is_valid = latest.volume >= 1.2 * average_volume
        if previous.close < vwap < latest.close and ema50 > ema200 and volume_is_valid:
            stop_loss = min(latest.low, vwap - atr * 0.25)
            risk = latest.close - stop_loss
            return StrategyDecision(
                should_enter=True,
                action="BUY",
                reason_codes=["VWAP_RECLAIM", "EMA_BULLISH", "VOLUME_CONFIRMATION"],
                price=latest.close,
                stop_loss=round(stop_loss, 4),
                take_profit=round(latest.close + risk * 2, 4),
                vwap=round(vwap, 4),
                ema50=round(ema50, 4),
                ema200=round(ema200, 4),
                opening_range_high=self._opening_high(session_bars),
                opening_range_low=self._opening_low(session_bars),
                volume=latest.volume,
                average_volume=round(average_volume, 4),
                atr=round(atr, 4),
                message="VWAP reclaim long setup qualified.",
                strategy_name="VWAP_RECLAIM_REJECT",
                score=82,
            )
        if previous.close > vwap > latest.close and ema50 < ema200 and volume_is_valid:
            stop_loss = max(latest.high, vwap + atr * 0.25)
            risk = stop_loss - latest.close
            return StrategyDecision(
                should_enter=True,
                action="SELL",
                reason_codes=["VWAP_REJECT", "EMA_BEARISH", "VOLUME_CONFIRMATION"],
                price=latest.close,
                stop_loss=round(stop_loss, 4),
                take_profit=round(latest.close - risk * 2, 4),
                vwap=round(vwap, 4),
                ema50=round(ema50, 4),
                ema200=round(ema200, 4),
                opening_range_high=self._opening_high(session_bars),
                opening_range_low=self._opening_low(session_bars),
                volume=latest.volume,
                average_volume=round(average_volume, 4),
                atr=round(atr, 4),
                message="VWAP reject short setup qualified.",
                strategy_name="VWAP_RECLAIM_REJECT",
                score=82,
            )
        return self.base._no_trade("No VWAP reclaim/reject setup qualified.", bars)

    def _ema_trend_pullback(self, bars: list[MarketBar]) -> StrategyDecision:
        context = self._context(bars)
        if context is None:
            return self.base._no_trade("EMA pullback indicator warmup incomplete.", bars)
        latest, previous, session_bars, vwap, ema50, ema200, atr, average_volume = context
        if not self._is_trade_time(latest):
            return self.base._no_trade("Outside regular market hours.", bars)

        volume_is_valid = latest.volume >= 1.1 * average_volume
        if ema50 > ema200 and latest.low <= ema50 < latest.close and latest.close > previous.close and latest.close > vwap and volume_is_valid:
            stop_loss = min(latest.low, ema50 - atr * 0.25)
            risk = latest.close - stop_loss
            return StrategyDecision(
                should_enter=True,
                action="BUY",
                reason_codes=["EMA_PULLBACK_LONG", "EMA_BULLISH", "VWAP_CONFIRMATION"],
                price=latest.close,
                stop_loss=round(stop_loss, 4),
                take_profit=round(latest.close + risk * 2, 4),
                vwap=round(vwap, 4),
                ema50=round(ema50, 4),
                ema200=round(ema200, 4),
                opening_range_high=self._opening_high(session_bars),
                opening_range_low=self._opening_low(session_bars),
                volume=latest.volume,
                average_volume=round(average_volume, 4),
                atr=round(atr, 4),
                message="EMA trend pullback long setup qualified.",
                strategy_name="EMA_TREND_PULLBACK",
                score=75,
            )
        if ema50 < ema200 and latest.high >= ema50 > latest.close and latest.close < previous.close and latest.close < vwap and volume_is_valid:
            stop_loss = max(latest.high, ema50 + atr * 0.25)
            risk = stop_loss - latest.close
            return StrategyDecision(
                should_enter=True,
                action="SELL",
                reason_codes=["EMA_PULLBACK_SHORT", "EMA_BEARISH", "VWAP_CONFIRMATION"],
                price=latest.close,
                stop_loss=round(stop_loss, 4),
                take_profit=round(latest.close - risk * 2, 4),
                vwap=round(vwap, 4),
                ema50=round(ema50, 4),
                ema200=round(ema200, 4),
                opening_range_high=self._opening_high(session_bars),
                opening_range_low=self._opening_low(session_bars),
                volume=latest.volume,
                average_volume=round(average_volume, 4),
                atr=round(atr, 4),
                message="EMA trend pullback short setup qualified.",
                strategy_name="EMA_TREND_PULLBACK",
                score=75,
            )
        return self.base._no_trade("No EMA trend pullback setup qualified.", bars)

    def _context(self, bars: list[MarketBar]):
        if len(bars) < 200:
            return None
        latest = bars[-1]
        previous = bars[-2]
        latest_date = latest.timestamp.astimezone(NY).date()
        session_bars = [bar for bar in bars if bar.timestamp.astimezone(NY).date() == latest_date]
        closes = [bar.close for bar in bars]
        vwap = self.base._session_vwap(session_bars)
        ema50 = self.base._ema(closes, 50)
        ema200 = self.base._ema(closes, 200)
        atr = self.base._atr(bars, 14)
        average_volume = self.base._sma([bar.volume for bar in bars], 20)
        if None in {vwap, ema50, ema200, atr, average_volume}:
            return None
        return latest, previous, session_bars, vwap, ema50, ema200, atr, average_volume

    def _is_trade_time(self, latest: MarketBar) -> bool:
        current = latest.timestamp.astimezone(NY).time()
        return time(9, 45) <= current < time(16, 0)

    def _opening_high(self, session_bars: list[MarketBar]) -> float | None:
        bars = [bar for bar in session_bars if time(9, 30) <= bar.timestamp.astimezone(NY).time() < time(9, 45)]
        return round(max((bar.high for bar in bars), default=0), 4) if bars else None

    def _opening_low(self, session_bars: list[MarketBar]) -> float | None:
        bars = [bar for bar in session_bars if time(9, 30) <= bar.timestamp.astimezone(NY).time() < time(9, 45)]
        return round(min((bar.low for bar in bars), default=0), 4) if bars else None
