from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.brokers.base import BrokerPosition
from app.db.sqlite import connect
from app.main import app
from app.services.reconciliation import reconcile_positions
from app.workers.analysis import run_once


def configure_test_database(path: Path) -> None:
    settings.__dict__.pop("database_path", None)
    settings.database_url = f"sqlite:///{path}"
    settings.paper_slippage_bps = 0
    settings.paper_commission_per_order = 0


def test_entry_exit_lifecycle_and_idempotency(tmp_path: Path) -> None:
    configure_test_database(tmp_path / "test.db")

    entry = {
        "ticker": "QQQ",
        "action": "BUY",
        "price": 500,
        "time": "2026-08-06T10:00:00-04:00",
        "reason_codes": ["VWAP_LONG"],
        "stop_loss": 498,
        "take_profit": 504,
        "event_id": "entry-1",
    }
    exit_event = {
        "ticker": "QQQ",
        "action": "SELL",
        "price": 504,
        "time": "2026-08-06T10:30:00-04:00",
        "reason_codes": ["TAKE_PROFIT"],
        "event_type": "EXIT",
        "event_id": "exit-1",
    }

    with TestClient(app) as client:
        assert client.post("/webhook/tradingview", json=entry).status_code == 200
        assert client.post("/webhook/tradingview", json=entry).status_code == 409
        assert client.post("/webhook/tradingview", json=exit_event).status_code == 200
        snapshot = client.get("/dashboard/snapshot").json()
        diagnostics = client.get("/diagnostics").json()
        deliveries = client.get("/webhooks/deliveries").json()
        failures = client.get("/webhooks/failures").json()
        assert run_once() is True

    assert snapshot["account"]["open_positions"] == 0
    assert snapshot["account"]["winning_trades"] == 1
    assert snapshot["account"]["realized_pnl"] == 80.0
    assert len(snapshot["closed_positions"]) == 1
    assert diagnostics["database_integrity"] == "ok"
    assert diagnostics["counts"]["trades"] == 2
    assert isinstance(diagnostics["configuration_warnings"], list)
    assert "analysis_queue" in diagnostics
    assert "stale_running_jobs" in diagnostics["analysis_queue"]
    assert [delivery["status"] for delivery in deliveries] == ["PROCESSED", "DUPLICATE", "PROCESSED"]
    assert [failure["status"] for failure in failures] == ["DUPLICATE"]


def test_costs_worker_journal_exports_and_reconciliation(tmp_path: Path) -> None:
    configure_test_database(tmp_path / "costs.db")
    settings.paper_slippage_bps = 10
    settings.paper_commission_per_order = 1
    entry = {
        "ticker": "QQQ", "action": "BUY", "price": 100,
        "time": "2026-08-06T10:00:00-04:00", "reason_codes": ["TEST"],
        "event_id": "cost-entry",
    }
    exit_event = {
        "ticker": "QQQ", "action": "SELL", "price": 110,
        "time": "2026-08-06T10:30:00-04:00", "reason_codes": ["TEST_EXIT"],
        "event_type": "EXIT", "event_id": "cost-exit",
    }
    with TestClient(app) as client:
        trade_id = client.post("/webhook/tradingview", json=entry).json()["id"]
        assert run_once() is True
        assert client.post("/webhook/tradingview", json=exit_event).status_code == 200
        journal = client.put(
            f"/journal/trades/{trade_id}",
            json={"notes": "Acceptance", "mistakes": "None", "lessons": "Follow rules", "tags": ["test"]},
        )
        assert journal.status_code == 200
        snapshot = client.get("/dashboard/snapshot").json()
        csv_export = client.get("/reports/trade-journal.csv")
        json_export = client.get("/reports/performance.json")
        performance_csv_export = client.get("/reports/performance.csv")

    position = snapshot["closed_positions"][0]
    assert round(position["entry_price"], 2) == 100.1
    assert round(position["exit_price"], 2) == 109.89
    assert position["realized_pnl"] < position["gross_pnl"]
    assert len(snapshot["equity_curve"]) == 1
    assert snapshot["analysis_queue"]["counts"]["COMPLETED"] == 1
    assert snapshot["analysis_queue"]["stale_running_jobs"] == 0
    assert isinstance(snapshot["configuration_warnings"], list)
    assert "Acceptance" in csv_export.text
    assert json_export.status_code == 200
    assert performance_csv_export.status_code == 200
    assert "realized_pnl" in performance_csv_export.text
    assert "analysis_pending_jobs" in performance_csv_export.text
    with connect(settings.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM trade_ai_analyses;").fetchone()[0] == 1

    class FakeBroker:
        def submit_order(self, order):  # pragma: no cover - contract placeholder
            raise NotImplementedError

        def list_positions(self):
            return [BrokerPosition(ticker="QQQ", side="LONG", quantity=1, average_price=100)]

    differences = reconcile_positions(settings.database_path, FakeBroker())
    assert len(differences) == 1
    assert differences[0].local_quantity == 0


def test_production_diagnostics_requires_secret(tmp_path: Path) -> None:
    configure_test_database(tmp_path / "diagnostics-auth.db")
    original_env = settings.app_env
    original_secret = settings.webhook_secret
    original_public_backend_url = settings.public_backend_url
    original_backend_cors_origins = settings.backend_cors_origins
    settings.__dict__.pop("cors_origins", None)
    settings.__dict__.pop("tradingview_webhook_url", None)
    settings.app_env = "production"
    settings.webhook_secret = "diagnostics-test-secret"
    settings.public_backend_url = "https://blackout.example.com"
    settings.backend_cors_origins = "https://dashboard.example.com"
    try:
        with TestClient(app) as client:
            rejected = client.get("/diagnostics")
            accepted = client.get(
                "/diagnostics",
                headers={"X-Blackout-Secret": "diagnostics-test-secret"},
            )
    finally:
        settings.app_env = original_env
        settings.webhook_secret = original_secret
        settings.public_backend_url = original_public_backend_url
        settings.backend_cors_origins = original_backend_cors_origins
        settings.__dict__.pop("cors_origins", None)
        settings.__dict__.pop("tradingview_webhook_url", None)

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["webhook_auth_configured"] is True


def test_bot_controls_default_stopped_and_start_stop(tmp_path: Path) -> None:
    configure_test_database(tmp_path / "bot-controls.db")
    original_mode = settings.execution_mode
    settings.execution_mode = "internal_paper"
    try:
        with TestClient(app) as client:
            initial = client.get("/bot/state")
            started = client.post("/bot/start")
            snapshot = client.get("/dashboard/snapshot")
            stopped = client.post("/bot/stop")
    finally:
        settings.execution_mode = original_mode

    assert initial.status_code == 200
    assert initial.json()["status"] == "STOPPED"
    assert started.json()["status"] == "RUNNING"
    assert snapshot.json()["bot_state"]["status"] == "RUNNING"
    assert stopped.json()["status"] == "STOPPED"


def test_alpaca_mode_does_not_submit_when_bot_stopped(tmp_path: Path) -> None:
    configure_test_database(tmp_path / "alpaca-stopped.db")
    original_mode = settings.execution_mode
    original_key = settings.alpaca_api_key
    original_secret = settings.alpaca_api_secret
    settings.execution_mode = "alpaca_paper"
    settings.alpaca_api_key = "paper-key"
    settings.alpaca_api_secret = "paper-secret"
    try:
        entry = {
            "ticker": "QQQ",
            "action": "BUY",
            "price": 500,
            "time": "2026-08-06T10:00:00-04:00",
            "reason_codes": ["VWAP_LONG"],
            "event_id": "alpaca-stopped-entry",
        }
        with TestClient(app) as client:
            assert client.post("/webhook/tradingview", json=entry).status_code == 200
            orders = client.get("/execution/orders").json()
    finally:
        settings.execution_mode = original_mode
        settings.alpaca_api_key = original_key
        settings.alpaca_api_secret = original_secret

    assert orders == []
