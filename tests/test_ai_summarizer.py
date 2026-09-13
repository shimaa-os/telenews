from datetime import datetime, timezone

import pytest

from app.models.news import ArabicBriefItem, BriefSummaries, NewsArticle
from app.services.ai_summarizer import AISummarizer


class FakeResponse:
    output_parsed = BriefSummaries(
        items=[
            ArabicBriefItem(
                article_index=1,
                headline_ar="عنوان عربي",
                summary_ar="ملخص عربي موثوق.",
                why_important_ar="لأنه مهم لدراسة هندسة الذكاء الاصطناعي.",
            )
        ]
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
        title="OpenAI releases model",
        description="New model release",
        source="OpenAI",
        url="https://example.com/story",
        published_at=datetime(2026, 9, 13, 5, 0, tzinfo=timezone.utc),
    )

    stories = await summarizer.summarize_news([article])

    assert stories[0].headline_ar == "عنوان عربي"
    assert client.responses.kwargs["text_format"] is BriefSummaries
    assert client.responses.kwargs["store"] is False
    assert "untrusted" in client.responses.kwargs["input"][0]["content"]
