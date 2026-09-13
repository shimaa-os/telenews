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


class BriefItem(BaseModel):
    """One structured English summary returned by the LLM."""

    article_index: int = Field(ge=1, le=10)
    headline: str = Field(min_length=1, max_length=180)
    summary: str = Field(min_length=1, max_length=700)
    why_important: str = Field(min_length=1, max_length=280)


# Backward-compat alias: old Arabic name now maps to English fields.
# Tests and old code importing ArabicBriefItem keep working.
class ArabicBriefItem(BaseModel):
    """Deprecated alias kept so old imports do not break."""

    article_index: int = Field(ge=1, le=10)
    headline_ar: str = Field(min_length=1, max_length=180)
    summary_ar: str = Field(min_length=1, max_length=700)
    why_important_ar: str = Field(min_length=1, max_length=280)


class BriefSummaries(BaseModel):
    """Validated batch of English summaries plus top story and market snapshot."""

    items: list[BriefItem] = Field(min_length=1, max_length=10)
    top_story_index: int = Field(ge=1, le=10)
    top_story_reason: str = Field(min_length=1, max_length=500)
    market_snapshot: str = Field(default="", max_length=500)


class BriefStory(BaseModel):
    """An original article paired with its validated English editorial copy."""

    article: NewsArticle
    headline: str
    summary: str
    why_important: str

    # Old Arabic attribute names still work (return English text).
    @property
    def headline_ar(self) -> str:
        return self.headline

    @property
    def summary_ar(self) -> str:
        return self.summary

    @property
    def why_important_ar(self) -> str:
        return self.why_important


class BriefResult(BaseModel):
    """Full brief: ranked stories plus top story and market snapshot."""

    stories: list[BriefStory] = Field(min_length=0, max_length=10)
    top_story_reason: str = Field(default="", max_length=500)
    market_snapshot: str = Field(default="", max_length=500)
