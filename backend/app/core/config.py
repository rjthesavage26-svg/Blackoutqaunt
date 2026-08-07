from functools import cached_property
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Blackout Quant"
    app_env: str = "development"
    database_url: str = "sqlite:///backend/data/blackout_quant.db"
    backend_cors_origins: str = "http://localhost:5173"
    public_backend_url: str = "http://localhost:8000"
    tradingview_enabled: bool = False
    tradingview_webhook_path: str = "/webhook/tradingview"
    log_level: str = "INFO"
    webhook_secret: str | None = None
    paper_starting_cash: float = Field(default=100_000.0, gt=0)
    paper_position_notional: float = Field(default=10_000.0, gt=0)
    paper_slippage_bps: float = Field(default=0.0, ge=0, le=1_000)
    paper_commission_per_order: float = Field(default=0.0, ge=0)
    analysis_worker_max_attempts: int = Field(default=3, ge=1, le=20)
    execution_mode: str = "internal_paper"
    alpaca_paper_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    alpaca_data_feed: str = "iex"
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    strategy_symbol: str = "QQQ"
    strategy_poll_seconds: int = Field(default=30, ge=5, le=300)

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8")

    @field_validator("app_env")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production.")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid.")
        return normalized

    @field_validator("execution_mode")
    @classmethod
    def validate_execution_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"internal_paper", "alpaca_paper"}:
            raise ValueError("EXECUTION_MODE must be internal_paper or alpaca_paper.")
        return normalized

    @cached_property
    def database_path(self) -> Path:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError("Only SQLite database URLs are supported in this project skeleton.")

        configured_path = Path(self.database_url.removeprefix(prefix))
        if configured_path.is_absolute():
            return configured_path

        backend_dir = Path(__file__).resolve().parents[2]
        project_root = backend_dir.parent

        # The project has used two relative database styles:
        # - backend/data/blackout_quant.db when running from the project root.
        # - data/blackout_quant.db when running from inside the backend folder.
        # Resolve both to the same backend/data location so the dashboard reads
        # the existing SQLite database instead of creating a second empty one.
        if configured_path.parts and configured_path.parts[0] == "backend":
            return project_root / configured_path

        return backend_dir / configured_path

    @cached_property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]

    @cached_property
    def tradingview_webhook_url(self) -> str:
        # TradingView needs one public HTTPS URL. Keeping it in settings lets
        # local development and production use different addresses without
        # changing code or the webhook payload schema.
        base_url = self.public_backend_url.rstrip("/")
        webhook_path = self.tradingview_webhook_path
        if not webhook_path.startswith("/"):
            webhook_path = f"/{webhook_path}"

        return f"{base_url}{webhook_path}"

    def runtime_warnings(self) -> list[str]:
        """Return non-fatal configuration warnings for diagnostics and startup logs."""
        warnings: list[str] = []
        parsed_public_url = urlparse(self.public_backend_url)
        secret = (self.webhook_secret or "").strip()

        if self.tradingview_enabled:
            if parsed_public_url.scheme != "https":
                warnings.append("PUBLIC_BACKEND_URL is not HTTPS; TradingView webhooks require public HTTPS.")
            if not secret:
                warnings.append("WEBHOOK_SECRET is not configured; webhook endpoint is unauthenticated.")
            elif secret == "replace-with-a-long-random-secret" or len(secret) < 16:
                warnings.append("WEBHOOK_SECRET is too weak for production use.")
            if not self.tradingview_webhook_path.startswith("/"):
                warnings.append("TRADINGVIEW_WEBHOOK_PATH should start with '/'.")
        if not self.cors_origins:
            warnings.append("BACKEND_CORS_ORIGINS is empty; browsers will not be allowed to call the API.")
        if "*" in self.cors_origins:
            warnings.append("BACKEND_CORS_ORIGINS contains '*'; restrict this before production.")
        if self.execution_mode == "alpaca_paper":
            if "paper-api.alpaca.markets" not in self.alpaca_paper_base_url:
                warnings.append("ALPACA_PAPER_BASE_URL must point to Alpaca paper trading, not live trading.")
            if not self.alpaca_api_key or not self.alpaca_api_secret:
                warnings.append("Alpaca paper execution is selected but API credentials are not configured.")
        if self.strategy_symbol.strip().upper() != "QQQ":
            warnings.append("STRATEGY_SYMBOL should remain QQQ for the current QQQ ORB strategy.")

        return warnings

    def production_errors(self) -> list[str]:
        """Return fatal production configuration problems."""
        if self.app_env != "production":
            return []

        return self.runtime_warnings()


settings = Settings()
