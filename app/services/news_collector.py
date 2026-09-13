"""Fault-tolerant RSS collection and article normalization."""

import asyncio
import calendar
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping

import feedparser
import httpx
from pydantic import ValidationError

from app.models.news import NewsArticle
from app.utils.logging import log_event
from app.utils.text_utils import clean_text


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RSSSource:
    """A named, explicitly trusted RSS endpoint."""

    name: str
    url: str


DEFAULT_SOURCES: tuple[RSSSource, ...] = (
    # GLOBAL NEWS
    RSSSource("Reuters", "https://www.reuters.com/rssFeed/businessNews"),
    RSSSource("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
    RSSSource("AP News", "https://apnews.com/index.xml"),
    RSSSource("The Guardian", "https://www.theguardian.com/world/rss"),
    RSSSource("CNN", "http://rss.cnn.com/rss/edition.rss"),
    RSSSource("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    # BUSINESS & FINANCE
    RSSSource("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss"),
    RSSSource("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    RSSSource("Financial Times", "https://www.ft.com/world?format=rss"),
    RSSSource("WSJ", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
    RSSSource("Forbes", "https://www.forbes.com/business/feed/"),
    # TECHNOLOGY & AI
    RSSSource("TechCrunch", "https://techcrunch.com/feed/"),
    RSSSource("The Verge", "https://www.theverge.com/rss/index.xml"),
    RSSSource("Wired", "https://www.wired.com/feed/rss"),
    RSSSource("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    RSSSource("MIT Technology Review", "https://www.technologyreview.com/feed/"),
    # SCIENCE & SPACE
    RSSSource("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    RSSSource("Scientific American", "https://www.scientificamerican.com/feed/"),
    # CRYPTO & DIGITAL ECONOMY
    RSSSource("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    RSSSource("CoinTelegraph", "https://cointelegraph.com/rss"),
)


def _parse_datetime(entry: Mapping[str, Any]) -> datetime | None:
    for parsed_key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(parsed_key)
        if parsed:
            try:
                return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            except (OverflowError, TypeError, ValueError):
                continue

    for text_key in ("published", "updated", "created"):
        value = str(entry.get(text_key) or "").strip()
        if not value:
            continue
        try:
            parsed_email_date = parsedate_to_datetime(value)
            if parsed_email_date.tzinfo is None:
                parsed_email_date = parsed_email_date.replace(tzinfo=timezone.utc)
            return parsed_email_date.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
                    timezone.utc
                )
            except (TypeError, ValueError):
                continue
    return None


class NewsCollector:
    """Collect and normalize articles from independent RSS feeds."""

    def __init__(
        self,
        *,
        sources: tuple[RSSSource, ...] = DEFAULT_SOURCES,
        timeout_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.sources = sources
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={
                "User-Agent": "AI-Morning-Brief/1.0 (+RSS reader)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
            },
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def collect_news(self) -> list[NewsArticle]:
        """Fetch all configured sources concurrently; one failure never stops the rest."""

        results = await asyncio.gather(
            *(self._collect_source(source) for source in self.sources),
            return_exceptions=True,
        )
        articles: list[NewsArticle] = []
        for source, result in zip(self.sources, results, strict=True):
            if isinstance(result, BaseException):
                log_event(
                    logger,
                    logging.ERROR,
                    "news_source_failed",
                    source=source.name,
                    error_type=type(result).__name__,
                )
                continue
            articles.extend(result)
        return articles

    async def _collect_source(self, source: RSSSource) -> list[NewsArticle]:
        try:
            response = await self.client.get(source.url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log_event(
                logger,
                logging.WARNING,
                "news_source_http_error",
                source=source.name,
                error_type=type(exc).__name__,
            )
            return []

        feed = await asyncio.to_thread(feedparser.parse, response.content)
        if getattr(feed, "bozo", False) and not feed.entries:
            log_event(
                logger,
                logging.WARNING,
                "news_source_parse_error",
                source=source.name,
            )
            return []

        normalized: list[NewsArticle] = []
        for entry in feed.entries:
            article = self.normalize_entry(entry, source.name)
            if article is not None:
                normalized.append(article)
        log_event(
            logger,
            logging.INFO,
            "news_source_collected",
            source=source.name,
            article_count=len(normalized),
        )
        return normalized

    @staticmethod
    def normalize_entry(
        entry: Mapping[str, Any], source_name: str
    ) -> NewsArticle | None:
        """Validate a feed entry and return a normalized article or ``None``."""

        title = clean_text(entry.get("title"), max_length=500)
        description = clean_text(
            entry.get("summary") or entry.get("description") or "",
            max_length=8_000,
        )
        url = str(entry.get("link") or "").strip()
        if not title or not url:
            return None
        try:
            return NewsArticle(
                title=title,
                description=description,
                source=source_name,
                url=url,
                published_at=_parse_datetime(entry),
            )
        except ValidationError:
            return None
