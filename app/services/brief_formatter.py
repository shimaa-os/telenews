"""Telegram-friendly plain-text brief formatting."""

from datetime import datetime

from app.models.news import BriefStory
from app.utils.text_utils import truncate


_NUMBER_EMOJIS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
_DIVIDER = "━━━━━━━━━━━━━━━━━━"


def format_telegram_message(
    stories: list[BriefStory],
    *,
    date: datetime,
    top_story_reason: str = "",
    market_snapshot: str = "",
) -> str:
    """Format up to ten validated stories as a concise English morning brief."""

    header = f"☀️ AI MORNING BRIEF\n📅 Date: {date:%Y-%m-%d}"
    blocks: list[str] = []
    for index, story in enumerate(stories, start=1):
        marker = _NUMBER_EMOJIS[index - 1] if index <= 10 else f"{index}."
        headline = getattr(story, "headline", None) or getattr(story, "headline_ar", "")
        summary = getattr(story, "summary", None) or getattr(story, "summary_ar", "")
        why_important = (
            getattr(story, "why_important", None) or getattr(story, "why_important_ar", "")
        )
        blocks.append(
            f"📰 {marker} {truncate(headline, 180)}\n\n"
            f"{truncate(summary, 700)}\n\n"
            f"💡 Why it matters:\n{truncate(why_important, 280)}\n\n"
            f"🔗 Source: {story.article.source}"
        )
    footer_parts = []
    if top_story_reason.strip():
        footer_parts.append(
            f"🔥 TOP STORY OF THE DAY\n{truncate(top_story_reason.strip(), 500)}"
        )
    if market_snapshot.strip():
        footer_parts.append(
            f"📊 QUICK MARKET SNAPSHOT\n{truncate(market_snapshot.strip(), 500)}"
        )
    footer_parts.append("🤖 Generated automatically by AI and X.com")
    footer = "\n\n".join(footer_parts)
    if not blocks:
        return f"{header}\n\nNo recent qualifying news for today.\n\n{footer}"
    return f"{header}\n\n{_DIVIDER}\n\n" + f"\n\n{_DIVIDER}\n\n".join(blocks) + f"\n\n{_DIVIDER}\n\n{footer}"
