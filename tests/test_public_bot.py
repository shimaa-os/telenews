from datetime import datetime, timedelta

import pytest

from app.config.settings import Settings
from app.scheduler.daily_job import BriefWorkflow, WorkflowResult
from app.services.telegram_poller import PublicBotPoller, parse_command


def test_parse_command_handles_variants():
    assert parse_command("/start") == "start"
    assert parse_command("/start@MyBot") == "start"
    assert parse_command("/news") == "news"
    assert parse_command("news") == "news"
    assert parse_command("  /HELP ") == "help"
    assert parse_command("hello") == "unknown"
    assert parse_command(None) == "unknown"


class FakeTelegram:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []
        self.client = FakeClient()

    async def send_to_chat(self, chat_id, message):
        self.sent.append((str(chat_id), message))
        return [1]

    async def close(self):
        pass


class FakeClient:
    async def aclose(self):
        pass


def _settings():
    return Settings(
        _env_file=None,
        OPENAI_API_KEY="sk-test",
        TELEGRAM_BOT_TOKEN="123:abc",
        TELEGRAM_CHAT_ID="999",
        OPENAI_MODEL="gpt-test",
    )


def _workflow_with_cache(fresh: bool):
    settings = _settings()
    workflow = BriefWorkflow.__new__(BriefWorkflow)
    workflow.settings = settings
    now = datetime.now(tz=settings.zoneinfo)
    finished = now if fresh else now - timedelta(hours=5)
    workflow.last_result = WorkflowResult(
        status="ok", started_at=finished, finished_at=finished, selected_count=1
    )
    workflow.last_message = "CACHED BRIEF"
    return workflow


@pytest.mark.asyncio
async def test_public_bot_sends_cached_brief_without_new_run():
    workflow = _workflow_with_cache(fresh=True)
    telegram = FakeTelegram()
    poller = PublicBotPoller(
        settings=workflow.settings, workflow=workflow, telegram=telegram
    )

    await poller.handle_message("999", "news")

    assert telegram.sent and telegram.sent[-1][1] == "CACHED BRIEF"


@pytest.mark.asyncio
async def test_public_bot_rate_limits_fast_repeats():
    workflow = _workflow_with_cache(fresh=True)
    telegram = FakeTelegram()
    poller = PublicBotPoller(
        settings=workflow.settings, workflow=workflow, telegram=telegram
    )

    await poller.handle_message("999", "/news")
    await poller.handle_message("999", "/news")

    assert "wait" in telegram.sent[-1][1].lower()


@pytest.mark.asyncio
async def test_private_bot_ignores_strangers():
    workflow = _workflow_with_cache(fresh=True)
    telegram = FakeTelegram()
    poller = PublicBotPoller(
        settings=workflow.settings, workflow=workflow, telegram=telegram
    )

    await poller.handle_message("111", "/news")

    assert telegram.sent == []
