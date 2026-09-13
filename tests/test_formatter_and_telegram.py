import json
from datetime import datetime, timezone

import httpx
import pytest

from app.models.news import BriefStory, NewsArticle
from app.services.brief_formatter import format_telegram_message
from app.services.telegram_service import TelegramService, split_message


def test_format_telegram_message_contains_expected_arabic_sections():
    article = NewsArticle(
        title="OpenAI releases model",
        description="details",
        source="OpenAI",
        url="https://example.com/openai",
        published_at=datetime(2026, 9, 13, 5, 0, tzinfo=timezone.utc),
    )
    story = BriefStory(
        article=article,
        headline_ar="خبر مهم عن OpenAI",
        summary_ar="ملخص عربي قصير عن الخبر.",
        why_important_ar="لأنه يؤثر على مطوري AI Agents.",
    )

    message = format_telegram_message(
        [story], date=datetime(2026, 9, 13, 8, 0, tzinfo=timezone.utc)
    )

    assert "AI Morning Brief" in message
    assert "الملخص" in message
    assert "ليه الخبر مهم" in message
    assert "https://example.com/openai" in message


def test_split_message_respects_telegram_limit_and_preserves_content():
    message = "A" * 120 + "\n\n" + "B" * 120 + "\n\n" + "C" * 120
    chunks = split_message(message, limit=150)

    assert len(chunks) == 3
    assert all(len(chunk) <= 150 for chunk in chunks)
    assert "\n\n".join(chunks) == message


@pytest.mark.asyncio
async def test_telegram_service_uses_bot_api_without_real_network():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert body["chat_id"] == "chat-1"
        assert body["disable_web_page_preview"] is True
        return httpx.Response(
            200,
            json={"ok": True, "result": {"message_id": len(requests)}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = TelegramService(bot_token="token", chat_id="chat-1", client=client)

    try:
        message_ids = await service.send_message("hello")
    finally:
        await service.close()
        await client.aclose()

    assert message_ids == [1]
    assert str(requests[0].url) == "https://api.telegram.org/bottoken/sendMessage"
