import logging
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    price REAL NOT NULL,
    timestamp TEXT NOT NULL,
    reason_codes TEXT NOT NULL,
    vwap REAL,
    ema50 REAL,
    ema200 REAL,
    opening_range_high REAL,
    opening_range_low REAL,
    volume REAL,
    average_volume REAL,
    atr REAL,
    stop_loss REAL,
    take_profit REAL,
    raw_payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_ai_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    trade_grade TEXT NOT NULL,
    confidence_score INTEGER NOT NULL,
    plain_english_explanation TEXT NOT NULL,
    why_the_trade_qualified TEXT NOT NULL,
    risk_factors TEXT NOT NULL,
    watch_after_entry TEXT NOT NULL,
    educational_summary TEXT NOT NULL,
    source_data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades (id)
);

CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_trade_id INTEGER NOT NULL UNIQUE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    entry_price REAL NOT NULL CHECK (entry_price > 0),
    stop_loss REAL,
    take_profit REAL,
    opened_at TEXT NOT NULL,
    exit_trade_id INTEGER UNIQUE,
    exit_price REAL,
    closed_at TEXT,
    realized_pnl REAL,
    close_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entry_trade_id) REFERENCES trades (id),
    FOREIGN KEY (exit_trade_id) REFERENCES trades (id)
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_status
ON paper_positions (status, opened_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_event_id
ON trades (event_id)
WHERE event_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    status TEXT NOT NULL,
    payload TEXT,
    error_message TEXT,
    trade_id INTEGER,
    response_status INTEGER NOT NULL,
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    FOREIGN KEY (trade_id) REFERENCES trades (id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_received
ON webhook_deliveries (received_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    available_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    locked_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades (id)
);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_claim
ON analysis_jobs (status, available_at, id);

CREATE TABLE IF NOT EXISTS trade_journal (
    trade_id INTEGER PRIMARY KEY,
    notes TEXT NOT NULL DEFAULT '',
    mistakes TEXT NOT NULL DEFAULT '',
    lessons TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades (id)
);

CREATE TABLE IF NOT EXISTS execution_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    client_order_id TEXT NOT NULL UNIQUE,
    execution_mode TEXT NOT NULL,
    broker TEXT NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    order_type TEXT NOT NULL DEFAULT 'market',
    status TEXT NOT NULL,
    broker_order_id TEXT,
    submitted_payload TEXT NOT NULL,
    response_payload TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades (id)
);

CREATE INDEX IF NOT EXISTS idx_execution_orders_trade
ON execution_orders (trade_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_execution_orders_status
ON execution_orders (status, created_at DESC);

CREATE TABLE IF NOT EXISTS bot_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    message TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategy_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    symbol TEXT NOT NULL,
    status TEXT NOT NULL,
    session_date TEXT,
    last_bar_at TEXT,
    opening_range_high REAL,
    opening_range_low REAL,
    latest_signal TEXT,
    message TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS strategy_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    score INTEGER NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    event_id TEXT NOT NULL,
    price REAL NOT NULL,
    stop_loss REAL,
    take_profit REAL,
    source_payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_signals_event_strategy
ON strategy_signals (event_id, strategy_name);

CREATE INDEX IF NOT EXISTS idx_strategy_signals_recent
ON strategy_signals (created_at DESC, id DESC);
"""


OPTIONAL_TRADE_COLUMNS = {
    "vwap": "REAL",
    "ema50": "REAL",
    "ema200": "REAL",
    "opening_range_high": "REAL",
    "opening_range_low": "REAL",
    "volume": "REAL",
    "average_volume": "REAL",
    "atr": "REAL",
    "stop_loss": "REAL",
    "take_profit": "REAL",
    "event_type": "TEXT NOT NULL DEFAULT 'ENTRY'",
    "quantity": "REAL",
    "event_id": "TEXT",
}

OPTIONAL_POSITION_COLUMNS = {
    "gross_pnl": "REAL",
    "entry_commission": "REAL NOT NULL DEFAULT 0",
    "exit_commission": "REAL NOT NULL DEFAULT 0",
    "slippage_cost": "REAL NOT NULL DEFAULT 0",
}

LOGGER = logging.getLogger(__name__)
LATEST_SCHEMA_VERSION = 3


def initialize_database(database_path: Path) -> None:
    # SQLite stores the whole database in one local file. Before connecting, we
    # make sure the folder exists so first-time setup works without manual steps.
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        # The schema creates any missing tables. It is safe to run on every app
        # startup because CREATE TABLE IF NOT EXISTS does not erase data.
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.execute("PRAGMA journal_mode = WAL;")
        connection.execute("PRAGMA busy_timeout = 5000;")
        # Add columns before creating indexes that reference them.
        before_event_index, after_event_index = SCHEMA.split(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_event_id", 1
        )
        connection.executescript(before_event_index)
        add_missing_trade_columns(connection)
        add_missing_columns(connection, "paper_positions", OPTIONAL_POSITION_COLUMNS)
        connection.executescript(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_event_id" + after_event_index
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO app_metadata (key, value)
            VALUES ('schema_version', '1');
            """
        )
        connection.execute(
            "UPDATE app_metadata SET value = ? WHERE key = 'schema_version';",
            (str(LATEST_SCHEMA_VERSION),),
        )
        LOGGER.info("database_initialized", extra={"database_path": str(database_path)})


def add_missing_trade_columns(connection: sqlite3.Connection) -> None:
    # Existing local databases may already have a trades table from Module 3.
    # SQLite will not add new columns through CREATE TABLE IF NOT EXISTS, so we
    # check the current columns and add only the optional fields that are missing.
    add_missing_columns(connection, "trades", OPTIONAL_TRADE_COLUMNS)


def add_missing_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name});").fetchall()
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};"
            )


def database_exists(database_path: Path) -> bool:
    return database_path.exists()


def connect(database_path: Path) -> sqlite3.Connection:
    # This helper keeps connection setup in one place. row_factory lets future
    # queries read rows like dictionaries instead of only tuple positions.
    connection = sqlite3.connect(database_path, timeout=5)
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA busy_timeout = 5000;")
    connection.row_factory = sqlite3.Row
    return connection
