import json
from pathlib import Path

from app.db.sqlite import connect
from app.models.journal import JournalEntry, JournalUpdate


class JournalRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def upsert(self, trade_id: int, update: JournalUpdate) -> JournalEntry | None:
        with connect(self.database_path) as connection:
            exists = connection.execute("SELECT id FROM trades WHERE id = ?;", (trade_id,)).fetchone()
            if exists is None:
                return None
            connection.execute(
                """
                INSERT INTO trade_journal (trade_id, notes, mistakes, lessons, tags)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(trade_id) DO UPDATE SET
                    notes = excluded.notes, mistakes = excluded.mistakes,
                    lessons = excluded.lessons, tags = excluded.tags,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (trade_id, update.notes, update.mistakes, update.lessons, json.dumps(update.tags)),
            )
            row = connection.execute("SELECT * FROM trade_journal WHERE trade_id = ?;", (trade_id,)).fetchone()
        data = dict(row)
        data["tags"] = json.loads(data["tags"])
        return JournalEntry(**data)

    def get(self, trade_id: int) -> JournalEntry | None:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM trade_journal WHERE trade_id = ?;", (trade_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["tags"] = json.loads(data["tags"])
        return JournalEntry(**data)
