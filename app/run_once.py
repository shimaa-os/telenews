"""One-shot runner for the AI Morning Brief.

Used by GitHub Actions (free daily cron) and for local manual runs.

Why this file exists:
- The FastAPI app in app/main.py + APScheduler needs a server running 24/7.
- For "just send me Telegram at 8am for free", a short script run once per day
  is simpler and needs no paid hosting.

Usage:
  python -m app.run_once            # full run, sends to Telegram
  python -m app.run_once --no-send  # safe test, runs everything except Telegram
"""

import argparse
import asyncio
import json
import logging
import sys

from app.config.settings import Settings
from app.scheduler.daily_job import BriefWorkflow
from app.utils.logging import configure_logging

logger = logging.getLogger(__name__)


async def _run(send_to_telegram: bool) -> int:
    settings = Settings()  # reads .env locally, or GitHub Secrets in Actions
    configure_logging(settings.log_level)

    workflow = BriefWorkflow(settings=settings)
    try:
        result = await workflow.run(send_to_telegram=send_to_telegram)
    except RuntimeError as exc:
        # Most common cause: missing OPENAI_API_KEY / TELEGRAM secrets.
        print(f"Brief failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await workflow.close()

    # Print a small JSON summary so it shows up in Actions logs.
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI Morning Brief once.")
    parser.add_argument(
        "--no-send",
        action="store_true",
        help="Run collection/ranking/summarization but skip Telegram delivery.",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(_run(send_to_telegram=not args.no_send))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
