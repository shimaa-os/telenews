from datetime import datetime, timedelta, timezone

from app.models.news import NewsArticle
from app.services.news_filter import filter_recent_news


def article(title: str, published_at):
    return NewsArticle(
        title=title,
        description="AI story",
        source="Test",
        url=f"https://example.com/{title}",
        published_at=published_at,
    )


def test_filter_recent_news_keeps_only_last_24_hours():
    now = datetime(2026, 9, 13, 8, 0, tzinfo=timezone.utc)
    recent = article("recent", now - timedelta(hours=3))
    old = article("old", now - timedelta(hours=25))
    undated = article("undated", None)
    future_skew = article("future", now + timedelta(minutes=10))

    result = filter_recent_news([recent, old, undated, future_skew], now=now)

    assert [item.title for item in result] == ["recent", "future"]
