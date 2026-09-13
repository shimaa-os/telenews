"""Small JSON logging setup with explicit structured fields."""

import json
import logging
from datetime import datetime, timezone
from typing import Any


_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JsonFormatter(logging.Formatter):
    """Format logs as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger without exposing application secrets."""

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # httpx logs full request URLs at INFO, and Telegram's bot token is part
    # of the URL path. Keep it at WARNING so tokens never appear in logs.
    for noisy in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: object,
) -> None:
    """Emit a structured event with non-sensitive fields."""

    logger.log(level, event, extra={"event": event, **fields})
