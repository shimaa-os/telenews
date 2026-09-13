from datetime import datetime, timedelta, timezone

from app.models.news import NewsArticle
from app.services.news_ranker import NewsRanker


def test_ranker_prefers_major_model_release_over_low_quality_listicle():
    now = datetime(2026, 9, 13, 8, 0, tzinfo=timezone.utc)
    release = NewsArticle(
        title="OpenAI releases new frontier model for AI agents",
        description="The new LLM includes an agent SDK, API updates, and benchmark results.",
        source="OpenAI",
        url="https://example.com/release",
        published_at=now - timedelta(hours=1),
    )
    listicle = NewsArticle(
        title="Top 10 best AI tools you need to know",
        description="A roundup of deals and sponsored tools.",
        source="Unknown Blog",
        url="https://example.com/listicle",
        published_at=now - timedelta(minutes=30),
    )

    ranked = NewsRanker().rank_news([listicle, release], now=now)

    assert ranked[0].title == release.title
    assert ranked[0].importance_score > ranked[1].importance_score
