from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.strategy.qqq_orb import MarketBar


class AlpacaMarketDataClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        api_secret: str,
        feed: str = "iex",
        timeout_seconds: float = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.feed = feed
        self.timeout_seconds = timeout_seconds

    def get_stock_bars(
        self,
        *,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "5Min",
        limit: int = 1000,
    ) -> list[MarketBar]:
        params = {
            "timeframe": timeframe,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": str(limit),
            "feed": self.feed,
            "adjustment": "raw",
            "sort": "asc",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.get(
                f"{self.base_url}/v2/stocks/{symbol}/bars",
                params=params,
                headers=self._headers(),
            )
        response.raise_for_status()
        payload = response.json()
        return [self._parse_bar(item) for item in payload.get("bars", [])]

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }

    def _parse_bar(self, item: dict[str, Any]) -> MarketBar:
        return MarketBar(
            timestamp=datetime.fromisoformat(item["t"].replace("Z", "+00:00")),
            open=float(item["o"]),
            high=float(item["h"]),
            low=float(item["l"]),
            close=float(item["c"]),
            volume=float(item["v"]),
        )
