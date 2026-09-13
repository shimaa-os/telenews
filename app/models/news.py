"""News and LLM response models."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, HttpUrl, field_validator


class NewsArticle(BaseModel):
    """Normalized article collected from an RSS source."""

    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=8_000)
    source: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    published_at: datetime | None = None
    importance_score: float = Field(default=0.0, ge=0.0, le=10.0)

    @field_validator("title", "description", "source", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("published_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ArabicBriefItem(BaseModel):
    """One structured Arabic summary returned by the LLM."""

    article_index: int = Field(ge=1, le=10)
    headline_ar: str = Field(min_length=1, max_length=180)
    summary_ar: str = Field(min_length=1, max_length=700)
    why_important_ar: str = Field(min_length=1, max_length=280)


class BriefSummaries(BaseModel):
    """Validated batch of Arabic summaries."""

    items: list[ArabicBriefItem] = Field(min_length=1, max_length=10)


class BriefStory(BaseModel):
    """An original article paired with its validated Arabic editorial copy."""

    article: NewsArticle
    headline_ar: str
    summary_ar: str
    why_important_ar: str
