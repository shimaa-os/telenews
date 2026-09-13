"""Public Telegram bot polling so ANY user with the bot username can use it.

How it works (beginner-friendly):
- Telegram keeps an inbox for your bot. `getUpdates` = "give me new messages".
- This loop asks every few seconds: "anyone new?". If yes, replies.
- /start or /news -> sends the latest cached brief (no new AI cost).
  Only if cache is older than BRIEF_CACHE_HOURS does it run a fresh workflow.
- This protects your OpenRouter quota from abuse when 100 people press /news.

Run always-on (needs 24/7 server, e.g. Render):
  python -m app.run_bot
"""

import asyncio
import logging
import time
from datetime import datetime

import httpx

from app.config.settings import Settings
from app.scheduler.daily_job import BriefWorkflow, WorkflowAlreadyRunning
from app.services.telegram_service import TelegramService
from app.utils.logging import log_event

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Welcome to AI Morning Brief!\n\n"
    "Send /news anytime to get the Top-10 latest global, business, tech, science and crypto brief.\n\n"
    "Daily auto-post is at 08:00 Cairo time.\n"
    "Generated automatically by AI and X.com"
)


def parse_command(text: str | None) -> str:
    """Return 'start', 'news', 'help', or 'unknown' for a Telegram message."""
    if not text:
        return "unknown"
    first_word = text.strip().split()[0].lower().split("@")[0]
    if first_word in ("/start", "start"):
        return "start"
    if first_word in ("/news", "news"):
        return "news"
    if first_word in ("/help", "help"):
        return "help"
    return "unknown"


class PublicBotPoller:
    """Poll getUpdates and reply to ANY chat with cached brief."""

    def __init__(
        self,
        *,
        settings: Settings,
        workflow: BriefWorkflow,
        telegram: TelegramService,
        cache_hours: float = 3.0,
    ) -> None:
        token = settings.require_telegram_credentials()[0]
        self.settings = settings
        self.workflow = workflow
        self.telegram = telegram
        self.cache_hours = cache_hours
        self._updates_url = f"https://api.telegram.org/bot{token}/getUpdates"
        self._offset: int = 0
        self._last_user_request: dict[str, float] = {}

    def _is_cache_fresh(self) -> bool:
        result = self.workflow.last_result
        message = self.workflow.last_message
        if not result or not message:
            return False
        age_seconds = (
            datetime.now(tz=self.settings.zoneinfo) - result.finished_at
        ).total_seconds()
        return age_seconds < self.cache_hours * 3600

    def _rate_limited(self, chat_id: str, cooldown: float = 30.0) -> bool:
        now = time.monotonic()
        last = self._last_user_request.get(chat_id, 0.0)
        if now - last < cooldown:
            return True
        self._last_user_request[chat_id] = now
        return False

    async def _get_brief_text(self) -> str:
        if self._is_cache_fresh() and self.workflow.last_message:
            return self.workflow.last_message
        try:
            await self.workflow.run(send_to_telegram=False)
        except WorkflowAlreadyRunning:
            # Daily job is running now; send whatever cache exists.
            if self.workflow.last_message:
                return self.workflow.last_message
            raise
        return self.workflow.last_message or "No recent qualifying news for today."

    async def handle_message(self, chat_id: str, text: str | None) -> None:
        command = parse_command(text)
        if command == "unknown":
            await self.telegram.send_to_chat(chat_id, WELCOME_MESSAGE)
            return
        if command == "help":
            await self.telegram.send_to_chat(chat_id, WELCOME_MESSAGE)
            return
        # start / news
        if self._rate_limited(chat_id):
            await self.telegram.send_to_chat(
                chat_id, "Please wait a few seconds before requesting again."
            )
            return
        try:
            brief = await self._get_brief_text()
        except Exception as exc:
            log_event(
                logger, logging.ERROR, "public_bot_brief_failed",
                error_type=type(exc).__name__,
            )
            await self.telegram.send_to_chat(
                chat_id, "Sorry, the brief is updating. Try /news again in a minute."
            )
            return
        if command == "start":
            await self.telegram.send_to_chat(chat_id, WELCOME_MESSAGE)
        await self.telegram.send_to_chat(chat_id, brief)
        log_event(logger, logging.INFO, "public_bot_replied", command=command)

    async def poll_once(self) -> None:
        try:
            response = await self.telegram.client.get(
                self._updates_url,
                params={"offset": self._offset, "timeout": 30},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log_event(
                logger, logging.WARNING, "public_bot_poll_failed",
                error_type=type(exc).__name__,
            )
            await asyncio.sleep(5)
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("result"), list):
            return
        for update in payload["result"]:
            update_id = update.get("update_id", 0)
            self._offset = max(self._offset, int(update_id) + 1)
            message = update.get("message") or update.get("edited_message") or {}
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is None:
                continue
            await self.handle_message(str(chat_id), message.get("text"))

    async def run_forever(self) -> None:
        log_event(logger, logging.INFO, "public_bot_started")
        while True:
            await self.poll_once()
