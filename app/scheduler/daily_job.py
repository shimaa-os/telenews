"""Daily AI news brief workflow and APScheduler integration."""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel

from app.config.settings import Settings
from app.models.news import NewsArticle
from app.services.ai_summarizer import AISummarizer
from app.services.brief_formatter import format_telegram_message
from app.services.news_collector import NewsCollector
from app.services.news_filter import filter_recent_news
from app.services.news_ranker import NewsRanker
from app.services.telegram_service import TelegramService
from app.utils.deduplication import remove_duplicates
from app.utils.logging import log_event


logger = logging.getLogger(__name__)


class WorkflowAlreadyRunning(RuntimeError):
    """Raised when a manual run overlaps an existing scheduled/manual run."""


class WorkflowResult(BaseModel):
    """Public summary of one workflow run."""

    status: str
    started_at: datetime
    finished_at: datetime
    collected_count: int = 0
    recent_count: int = 0
    deduplicated_count: int = 0
    selected_count: int = 0
    telegram_messages_sent: int = 0
    delivered_to_telegram: bool = False


class BriefWorkflow:
    """Coordinate collection, filtering, ranking, summarization, and delivery."""

    def __init__(
        self,
        *,
        settings: Settings,
        collector: NewsCollector | None = None,
        ranker: NewsRanker | None = None,
    ) -> None:
        self.settings = settings
        self.collector = collector or NewsCollector(
            timeout_seconds=settings.request_timeout_seconds
        )
        self.ranker = ranker or NewsRanker()
        self.latest_news: list[NewsArticle] = []
        self.last_result: WorkflowResult | None = None
        self.last_message: str | None = None
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self.collector.close()

    async def run(self, *, send_to_telegram: bool = True) -> WorkflowResult:
        if self._lock.locked():
            raise WorkflowAlreadyRunning("AI Morning Brief is already running")

        async with self._lock:
            started_at = datetime.now(tz=self.settings.zoneinfo)
            log_event(logger, logging.INFO, "workflow_started", started_at=started_at.isoformat())

            articles = await self.collector.collect_news()
            recent = filter_recent_news(
                articles,
                lookback_hours=self.settings.news_lookback_hours,
                now=started_at,
            )
            deduplicated = remove_duplicates(recent)
            ranked = self.ranker.rank_news(deduplicated)
            selected = ranked[: self.settings.max_news_items]
            self.latest_news = ranked

            log_event(
                logger,
                logging.INFO,
                "workflow_articles_selected",
                collected_count=len(articles),
                recent_count=len(recent),
                deduplicated_count=len(deduplicated),
                selected_count=len(selected),
            )

            if selected:
                summarizer = AISummarizer(
                    api_key=self.settings.require_openai_key(),
                    model=self.settings.openai_model,
                    base_url=self.settings.openai_base_url,
                )
                try:
                    brief_result = await summarizer.summarize_news(selected)
                finally:
                    await summarizer.close()
                stories = brief_result.stories
                top_story_reason = brief_result.top_story_reason
                market_snapshot = brief_result.market_snapshot
            else:
                stories = []
                top_story_reason = ""
                market_snapshot = ""

            message = format_telegram_message(
                stories,
                date=started_at,
                top_story_reason=top_story_reason,
                market_snapshot=market_snapshot,
            )
            self.last_message = message
            telegram_messages_sent = 0

            if send_to_telegram:
                bot_token, chat_id = self.settings.require_telegram_credentials()
                telegram = TelegramService(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    timeout_seconds=self.settings.request_timeout_seconds,
                )
                try:
                    responses = await telegram.send_message(message)
                    telegram_messages_sent = len(responses)
                finally:
                    await telegram.close()

            finished_at = datetime.now(tz=self.settings.zoneinfo)
            result = WorkflowResult(
                status="ok",
                started_at=started_at,
                finished_at=finished_at,
                collected_count=len(articles),
                recent_count=len(recent),
                deduplicated_count=len(deduplicated),
                selected_count=len(selected),
                telegram_messages_sent=telegram_messages_sent,
                delivered_to_telegram=send_to_telegram,
            )
            self.last_result = result
            log_event(
                logger,
                logging.INFO,
                "workflow_finished",
                **result.model_dump(mode="json"),
            )
            return result


async def run_daily_ai_news_brief(workflow: BriefWorkflow) -> None:
    """APScheduler entrypoint for the daily Telegram delivery."""

    try:
        await workflow.run(send_to_telegram=True)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "workflow_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise


def create_scheduler(settings: Settings, workflow: BriefWorkflow) -> AsyncIOScheduler:
    """Create the Cairo 08:00 daily scheduler."""

    scheduler = AsyncIOScheduler(timezone=settings.zoneinfo)
    trigger = CronTrigger(hour=8, minute=0, timezone=settings.zoneinfo)
    scheduler.add_job(
        run_daily_ai_news_brief,
        trigger,
        args=[workflow],
        id="daily-ai-morning-brief",
        name="Daily AI Morning Brief",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3_600,
        replace_existing=True,
    )
    return scheduler
