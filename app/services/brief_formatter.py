"""Telegram-friendly plain-text brief formatting."""

from datetime import datetime

from app.models.news import BriefStory
from app.utils.text_utils import truncate


_NUMBER_EMOJIS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟")
_DIVIDER = "━━━━━━━━━━━━━━"


def format_telegram_message(
    stories: list[BriefStory], *, date: datetime
) -> str:
    """Format at most ten validated stories as a concise Arabic morning brief."""

    header = f"☀️ AI Morning Brief\n\n📅 {date:%Y-%m-%d}"
    blocks: list[str] = []
    for index, story in enumerate(stories, start=1):
        marker = _NUMBER_EMOJIS[index - 1]
        blocks.append(
            f"{marker} {truncate(story.headline_ar, 180)}\n\n"
            f"📝 الملخص:\n{truncate(story.summary_ar, 700)}\n\n"
            f"💡 ليه الخبر مهم؟\n{truncate(story.why_important_ar, 280)}\n\n"
            f"🏢 المصدر:\n{story.article.source}\n\n"
            f"🔗 اقرأ الخبر:\n{story.article.url}"
        )
    footer = "🤖 تم إعداد النشرة تلقائيًا بواسطة AI Morning Brief."
    if not blocks:
        return f"{header}\n\nلا توجد أخبار حديثة مؤهلة للنشرة اليوم.\n\n{footer}"
    return f"{header}\n\n" + f"\n\n{_DIVIDER}\n\n".join(blocks) + f"\n\n{footer}"
