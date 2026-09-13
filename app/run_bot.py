"""Always-on private bot runner: ONLY owner chat can trigger it.

Usage:
  python -m app.run_bot            # polls forever, replies when YOU send news
  python -m app.run_bot --once     # fetch one batch then exit (test mode)

Send "news" or /news in Telegram and it replies with the Top-10 brief.
Anyone else messaging is ignored.

Needs 24/7 to listen: keep this running on your PC for testing,
or host on Render/Railway/Fly. GitHub Actions free CANNOT listen
because it exits after one run.
"""

import argparse
import asyncio

from app.config.settings import Settings
from app.scheduler.daily_job import BriefWorkflow
from app.services.telegram_poller import PublicBotPoller
from app.services.telegram_service import TelegramService
from app.utils.logging import configure_logging


async def _run(once: bool, cache_hours: float) -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    bot_token, owner_chat = settings.require_telegram_credentials()
    workflow = BriefWorkflow(settings=settings)
    telegram = TelegramService(
        bot_token=bot_token,
        chat_id=owner_chat,
        timeout_seconds=settings.request_timeout_seconds,
    )
    poller = PublicBotPoller(
        settings=settings, workflow=workflow, telegram=telegram, cache_hours=cache_hours
    )
    try:
        if once:
            await poller.poll_once()
        else:
            await poller.run_forever()
    finally:
        await telegram.close()
        await workflow.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the public Telegram bot.")
    parser.add_argument("--once", action="store_true", help="Poll one batch then exit.")
    parser.add_argument(
        "--cache-hours",
        type=float,
        default=3.0,
        help="Reuse cached brief for this many hours (saves AI cost).",
    )
    args = parser.parse_args()
    asyncio.run(_run(once=args.once, cache_hours=args.cache_hours))


if __name__ == "__main__":
    main()
