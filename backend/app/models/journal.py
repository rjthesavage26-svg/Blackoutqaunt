from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class JournalUpdate(BaseModel):
    notes: str = Field(default="", max_length=20_000)
    mistakes: str = Field(default="", max_length=20_000)
    lessons: str = Field(default="", max_length=20_000)
    tags: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))


class JournalEntry(JournalUpdate):
    trade_id: int
    created_at: datetime
    updated_at: datetime
