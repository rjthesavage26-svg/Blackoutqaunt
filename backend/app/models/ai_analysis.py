from pydantic import BaseModel, Field


class TradeAnalysisDraft(BaseModel):
    # The worker creates this model before saving it. It holds the educational
    # analysis text and the data snapshot used to create that analysis.
    trade_id: int
    trade_grade: str = Field(pattern="^[A-F]$")
    confidence_score: int = Field(ge=0, le=100)
    plain_english_explanation: str
    why_the_trade_qualified: str
    risk_factors: str
    watch_after_entry: str
    educational_summary: str
    source_data: dict


class SavedTradeAnalysis(TradeAnalysisDraft):
    # This is the stored database version. A trade may have more than one saved
    # analysis later if the user chooses to regenerate explanations.
    id: int
