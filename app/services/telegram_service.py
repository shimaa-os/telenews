"""Telegram Bot API delivery with safe message splitting."""

import logging
from typing import Any

import httpx

from app.utils.logging import log_event


logger = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 4_096


def _split_oversized_segment(segment: str, limit: int) -> list[str]:
    chunks: list[str] = []
    remaining = segment.strip()
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at < limit // 2:
            split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def split_message(message: str, *, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split text on paragraph boundaries while guaranteeing Telegram's size limit."""

    if limit < 32:
        raise ValueError("Message split limit must be at least 32 characters")
    if len(message) <= limit:
        return [message]

    segments: list[str] = []
    for paragraph in message.split("\n\n"):
        segments.extend(_split_oversized_segment(paragraph, limit))

    chunks: list[str] = []
    current = ""
    for segment in segments:
        candidate = f"{current}\n\n{segment}" if current else segment
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = segment
    if current:
        chunks.append(current)
    return chunks


class TelegramService:
    """Send plain-text messages through Telegram without logging credentials."""

    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        timeout_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not bot_token or not chat_id:
            raise ValueError("Telegram bot token and chat ID are required")
        self._send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds))

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def send_message(self, message: str) -> list[int]:
        """Send one logical message as one or more Telegram-safe chunks."""

        message_ids: list[int] = []
        chunks = split_message(message)
        for part_number, chunk in enumerate(chunks, start=1):
            try:
                response = await self.client.post(
                    self._send_url,
                    json={
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "disable_web_page_preview": True,
                    },
                )
                response.raise_for_status()
                payload: Any = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    "telegram_send_failed",
                    part_number=part_number,
                    error_type=type(exc).__name__,
                )
                raise RuntimeError("Telegram delivery failed") from exc

            if not isinstance(payload, dict) or payload.get("ok") is not True:
                log_event(
                    logger,
                    logging.ERROR,
                    "telegram_api_rejected_message",
                    part_number=part_number,
                )
                raise RuntimeError("Telegram rejected the message; check bot credentials and chat ID")
            result = payload.get("result")
            if isinstance(result, dict) and isinstance(result.get("message_id"), int):
                message_ids.append(result["message_id"])

        log_event(
            logger,
            logging.INFO,
            "telegram_send_succeeded",
            message_count=len(chunks),
        )
        return message_ids
