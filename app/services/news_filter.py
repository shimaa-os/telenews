"""Publication-time filtering."""

from datetime import datetime, timedelta, timezone

from app.models.news import NewsArticle


def filter_recent_news(
    articles: list[NewsArticle],
    *,
    lookback_hours: int = 24,
    now: datetime | None = None,
) -> list[NewsArticle]:
    """Keep dated articles inside the lookback window, allowing slight clock skew."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    reference = reference.astimezone(timezone.utc)
    cutoff = reference - timedelta(hours=lookback_hours)
    future_tolerance = reference + timedelta(minutes=15)
    return [
        article
        for article in articles
        if article.published_at is not None
        and cutoff <= article.published_at <= future_tolerance
    ]
