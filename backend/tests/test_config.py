from app.core.config import Settings


def test_development_runtime_warnings_are_non_fatal() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        tradingview_enabled=True,
        public_backend_url="http://localhost:8000",
        webhook_secret="",
    )

    warnings = settings.runtime_warnings()

    assert any("PUBLIC_BACKEND_URL is not HTTPS" in warning for warning in warnings)
    assert any("WEBHOOK_SECRET is not configured" in warning for warning in warnings)
    assert settings.production_errors() == []


def test_production_errors_reject_unsafe_public_runtime_config() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        tradingview_enabled=True,
        public_backend_url="http://localhost:8000",
        backend_cors_origins="*",
        webhook_secret="short",
    )

    errors = settings.production_errors()

    assert any("PUBLIC_BACKEND_URL is not HTTPS" in error for error in errors)
    assert any("WEBHOOK_SECRET is too weak" in error for error in errors)
    assert any("BACKEND_CORS_ORIGINS contains '*'" in error for error in errors)


def test_production_config_accepts_https_secret_and_restricted_cors() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        tradingview_enabled=True,
        public_backend_url="https://blackout.example.com",
        backend_cors_origins="https://dashboard.example.com",
        webhook_secret="long-random-secret-value",
    )

    assert settings.runtime_warnings() == []
    assert settings.production_errors() == []
