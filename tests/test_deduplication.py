from datetime import datetime, timezone

from app.models.news import NewsArticle
from app.utils.deduplication import canonicalize_url, remove_duplicates, title_similarity


def make_article(title: str, url: str, description: str = "short") -> NewsArticle:
    return NewsArticle(
        title=title,
        description=description,
        source="OpenAI",
        url=url,
        published_at=datetime(2026, 9, 13, 7, 0, tzinfo=timezone.utc),
    )


def test_canonicalize_url_removes_tracking_and_fragments():
    assert (
        canonicalize_url("https://Example.com/news/?utm_source=x&keep=1#section")
        == "https://example.com/news?keep=1"
    )


def test_remove_duplicates_handles_exact_urls_and_keeps_richer_article():
    short = make_article("OpenAI releases new GPT model", "https://example.com/a?utm_source=rss")
    rich = make_article(
        "OpenAI releases new GPT model",
        "https://example.com/a",
        description="much richer article description",
    )

    result = remove_duplicates([short, rich])

    assert len(result) == 1
    assert result[0].description == "much richer article description"


def test_title_similarity_catches_near_duplicate_ai_release_titles():
    left = "OpenAI releases new GPT model"
    right = "OpenAI announces newest GPT model release"

    assert title_similarity(left, right) >= 0.84
