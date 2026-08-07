import json
from pathlib import Path

from app.db.sqlite import connect
from app.models.ai_analysis import SavedTradeAnalysis, TradeAnalysisDraft


class AIAnalysisRepository:
    # This repository owns database reads and writes for analysis work. Keeping
    # it separate from the trade repository makes regeneration easier later.
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_trade_by_id(self, trade_id: int) -> dict | None:
        # The worker reads the stored trade from SQLite instead of trusting a
        # webhook object in memory. That keeps analysis tied to saved data.
        with connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    ticker,
                    action,
                    price,
                    timestamp,
                    reason_codes,
                    vwap,
                    ema50,
                    ema200,
                    opening_range_high,
                    opening_range_low,
                    volume,
                    average_volume,
                    atr,
                    stop_loss,
                    take_profit,
                    raw_payload,
                    created_at
                FROM trades
                WHERE id = ?;
                """,
                (trade_id,),
            ).fetchone()

        if row is None:
            return None

        trade = dict(row)
        trade["reason_codes"] = json.loads(trade["reason_codes"])
        trade["raw_payload"] = json.loads(trade["raw_payload"])
        return trade

    def save_analysis(self, analysis: TradeAnalysisDraft) -> SavedTradeAnalysis:
        # Regeneration is supported by inserting a new row each time. Existing
        # analyses and the original trade record are left untouched.
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO trade_ai_analyses (
                    trade_id,
                    trade_grade,
                    confidence_score,
                    plain_english_explanation,
                    why_the_trade_qualified,
                    risk_factors,
                    watch_after_entry,
                    educational_summary,
                    source_data
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    analysis.trade_id,
                    analysis.trade_grade,
                    analysis.confidence_score,
                    analysis.plain_english_explanation,
                    analysis.why_the_trade_qualified,
                    analysis.risk_factors,
                    analysis.watch_after_entry,
                    analysis.educational_summary,
                    json.dumps(analysis.source_data),
                ),
            )

            analysis_id = cursor.lastrowid

        return SavedTradeAnalysis(id=analysis_id, **analysis.model_dump())
