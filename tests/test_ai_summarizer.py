from datetime import datetime, timezone

import pytest

from app.models.news import BriefItem, BriefSummaries, NewsArticle
from app.services.ai_summarizer import AISummarizer


class FakeResponse:
    output_parsed = BriefSummaries(
        items=[
            BriefItem(
                article_index=1,
                headline="Major market rally",
                summary="Markets rose on fresh economic data. Investors reacted positively.",
                why_important="It affects global portfolios and rates.",
            )
        ],
        top_story_index=1,
        top_story_reason="It moves markets and policy worldwide.",
        market_snapshot="",
    )


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


@pytest.mark.asyncio
async def test_ai_summarizer_uses_structured_parse_without_external_call():
    client = FakeClient()
    summarizer = AISummarizer(api_key="test", model="gpt-test", client=client)
    article = NewsArticle(
        title="Markets rally on rates outlook",
        description="Stocks rose after new data",
        source="Reuters",
        url="https://example.com/story",
        published_at=datetime(2026, 9, 13, 5, 0, tzinfo=timezone.utc),
    )

    result = await summarizer.summarize_news([article])

    assert result.stories[0].headline == "Major market rally"
    assert result.top_story_reason == "It moves markets and policy worldwide."
    assert client.responses.kwargs["text_format"] is BriefSummaries
    assert client.responses.kwargs["store"] is False
    assert "untrusted" in client.responses.kwargs["input"][0]["content"]
