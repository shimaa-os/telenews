"""FastAPI application for AI Morning Brief."""

import hmac
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from app.config.settings import Settings, get_settings
from app.scheduler.daily_job import (
    BriefWorkflow,
    WorkflowAlreadyRunning,
    WorkflowResult,
    create_scheduler,
)
from app.services.telegram_service import TelegramService
from app.utils.logging import configure_logging, log_event


logger = logging.getLogger(__name__)


async def require_api_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Require bearer auth only when API_BEARER_TOKEN is configured."""

    settings: Settings = request.app.state.settings
    if settings.api_bearer_token is None:
        return

    expected = settings.api_bearer_token.get_secret_value()
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()

    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI app with scheduler lifecycle."""

    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        workflow = BriefWorkflow(settings=app_settings)
        scheduler = create_scheduler(app_settings, workflow)
        app.state.settings = app_settings
        app.state.workflow = workflow
        app.state.scheduler = scheduler
        scheduler.start()
        log_event(logger, logging.INFO, "scheduler_started", timezone=app_settings.timezone)
        try:
            yield
        finally:
            scheduler.shutdown(wait=False)
            await workflow.close()
            log_event(logger, logging.INFO, "scheduler_stopped")

    app = FastAPI(
        title="AI Morning Brief",
        description="Daily AI news brief automation for Arabic Telegram delivery.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health(request: Request) -> dict[str, object]:
        scheduler = request.app.state.scheduler
        workflow: BriefWorkflow = request.app.state.workflow
        job = scheduler.get_job("daily-ai-morning-brief")
        next_run_time = job.next_run_time.isoformat() if job and job.next_run_time else None
        return {
            "status": "ok",
            "scheduler_running": scheduler.running,
            "next_run_time": next_run_time,
            "timezone": app_settings.timezone,
            "openai_configured": app_settings.openai_api_key is not None,
            "telegram_configured": bool(
                app_settings.telegram_bot_token and app_settings.telegram_chat_id
            ),
            "last_result": workflow.last_result.model_dump(mode="json")
            if workflow.last_result
            else None,
        }

    @app.post("/run-news-brief", dependencies=[Depends(require_api_token)])
    async def run_news_brief(request: Request) -> WorkflowResult:
        workflow: BriefWorkflow = request.app.state.workflow
        try:
            return await workflow.run(send_to_telegram=True)
        except WorkflowAlreadyRunning as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    @app.get("/news")
    async def news(request: Request) -> dict[str, object]:
        workflow: BriefWorkflow = request.app.state.workflow
        return {
            "count": len(workflow.latest_news),
            "items": [item.model_dump(mode="json") for item in workflow.latest_news],
        }

    @app.post("/telegram/test", dependencies=[Depends(require_api_token)])
    async def telegram_test(request: Request) -> dict[str, object]:
        bot_token, chat_id = app_settings.require_telegram_credentials()
        telegram = TelegramService(
            bot_token=bot_token,
            chat_id=chat_id,
            timeout_seconds=app_settings.request_timeout_seconds,
        )
        try:
            responses = await telegram.send_message(
                "AI Morning Brief: Telegram connection is working."
            )
        finally:
            await telegram.close()
        return {"status": "ok", "messages_sent": len(responses)}

    return app


app = create_app()
