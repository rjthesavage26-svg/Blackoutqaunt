from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TradingViewAlert(BaseModel):
    # This model describes the JSON shape we expect from TradingView. FastAPI
    # uses it to reject missing fields, wrong data types, and invalid values
    # before anything is saved to SQLite.
    ticker: str
    action: Literal["BUY", "SELL"]
    price: float = Field(gt=0)
    time: datetime
    reason_codes: list[str] = Field(min_length=1)
    vwap: float | None = Field(default=None, gt=0)
    ema50: float | None = Field(default=None, gt=0)
    ema200: float | None = Field(default=None, gt=0)
    opening_range_high: float | None = Field(default=None, gt=0)
    opening_range_low: float | None = Field(default=None, gt=0)
    volume: float | None = Field(default=None, ge=0)
    average_volume: float | None = Field(default=None, ge=0)
    atr: float | None = Field(default=None, ge=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    event_type: Literal["ENTRY", "EXIT"] = "ENTRY"
    quantity: float | None = Field(default=None, gt=0)
    event_id: str | None = Field(default=None, min_length=1, max_length=200)

    model_config = ConfigDict(populate_by_name=True)

    @property
    def timestamp(self) -> datetime:
        """Internal name retained without changing the public `time` field."""
        return self.time

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        # Blackout Quant's first strategy is QQQ-only, so the webhook accepts
        # only QQQ alerts in this module.
        normalized_ticker = value.strip().upper()
        if normalized_ticker != "QQQ":
            raise ValueError("Only QQQ alerts are supported.")
        return normalized_ticker

    @field_validator("reason_codes")
    @classmethod
    def validate_reason_codes(cls, value: list[str]) -> list[str]:
        # Reason codes explain why the strategy created an alert. Empty reason
        # codes are not useful for learning or later review, so they are rejected.
        cleaned_reason_codes = [reason_code.strip() for reason_code in value if reason_code.strip()]
        if not cleaned_reason_codes:
            raise ValueError("At least one reason code is required.")
        return cleaned_reason_codes


class SavedTrade(BaseModel):
    # This is the small response returned after a valid alert is saved.
    id: int
    ticker: str
    action: str
    price: float
    timestamp: datetime
    reason_codes: list[str]
    vwap: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    opening_range_high: float | None = None
    opening_range_low: float | None = None
    volume: float | None = None
    average_volume: float | None = None
    atr: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


RawPayload = dict[str, Any]
