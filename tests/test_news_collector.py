from datetime import datetime, timezone

from app.services.news_collector import NewsCollector


def test_normalize_entry_strips_html_and_parses_dates():
    entry = {
        "title": "<b>OpenAI launches model</b>",
        "summary": "<p>New API features for developers.</p>",
        "link": "https://example.com/story",
        "published": "Sun, 13 Sep 2026 05:30:00 GMT",
    }

    article = NewsCollector.normalize_entry(entry, "OpenAI")

    assert article is not None
    assert article.title == "OpenAI launches model"
    assert article.description == "New API features for developers."
    assert article.published_at == datetime(2026, 9, 13, 5, 30, tzinfo=timezone.utc)


def test_normalize_entry_rejects_missing_url():
    assert NewsCollector.normalize_entry({"title": "No URL"}, "Test") is None
