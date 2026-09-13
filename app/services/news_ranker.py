"""Transparent deterministic importance scoring for general news."""

from datetime import datetime, timezone

from app.models.news import NewsArticle


_TOPIC_WEIGHTS: tuple[tuple[tuple[str, ...], float], ...] = (
    (("breaking", "urgent", "developing story", "just in"), 3.5),
    (("election", "president", "prime minister", "parliament", "ceasefire", "war ", "peace deal"), 3.0),
    (("federal reserve", "interest rate", "inflation", "recession", "gdp", "stock market", "central bank"), 3.0),
    (("foundation model", "frontier model", "large language model", " llm"), 2.8),
    (("model release", "new model", "launches model", "releases model"), 2.5),
    (("ai agent", "agentic ai", "multi-agent", "agent sdk"), 2.4),
    (("bitcoin", "ethereum", "crypto", "etf inflow", "halving"), 2.4),
    (("nasa", "spacex", "moon landing", "mars", "satellite launch"), 2.2),
    (("regulation", "ai act", "legislation", "executive order", "sanctions"), 2.0),
    (("benchmark", "research", "paper", "transformer", "clinical trial", "vaccine"), 1.8),
    (("ai safety", "alignment", "red teaming", "model safety"), 1.8),
    (("acquisition", "acquires", "merger", "partnership", "partners with", "ipo"), 1.6),
    (("developer", " api", "sdk", "open source", "fine-tuning", " rag"), 1.5),
)

_ENTITY_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("openai", 1.5),
    ("anthropic", 1.4),
    ("claude", 1.3),
    ("deepmind", 1.3),
    ("gemini", 1.3),
    ("federal reserve", 1.4),
    ("white house", 1.2),
    ("tesla", 1.0),
    ("apple", 1.0),
    ("microsoft", 1.0),
    ("nvidia", 1.0),
    ("bitcoin", 1.2),
)

_SOURCE_WEIGHTS = {
    "Reuters": 1.3,
    "BBC News": 1.3,
    "AP News": 1.3,
    "The Guardian": 1.2,
    "CNN": 1.1,
    "Al Jazeera": 1.2,
    "Bloomberg": 1.3,
    "CNBC": 1.2,
    "Financial Times": 1.3,
    "WSJ": 1.3,
    "Forbes": 1.1,
    "TechCrunch": 1.0,
    "The Verge": 0.9,
    "Wired": 1.0,
    "Ars Technica": 1.0,
    "MIT Technology Review": 1.1,
    "NASA": 1.2,
    "Scientific American": 1.1,
    "CoinDesk": 1.0,
    "CoinTelegraph": 0.9,
}

_LOW_QUALITY_PHRASES = (
    "opinion:",
    "sponsored",
    "you won't believe",
    "what you need to know",
    "best ai tools",
    "deal",
    "sale",
    "horoscope",
    "crossword",
)

_MAJOR_ACTIONS = (
    "announce",
    "launch",
    "release",
    "introduce",
    "unveil",
    "open source",
    "acquire",
    "partner",
)


class NewsRanker:
    """Score news with explainable signals and return a stable ordering."""

    def score_article(
        self, article: NewsArticle, *, now: datetime | None = None
    ) -> float:
        reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        text = f" {article.title} {article.description}".casefold()
        # X sources are dynamic (X @handle) - give them a solid breaking-news weight.
        if article.source.startswith("X @"):
            base_source_weight = 1.1
        else:
            base_source_weight = _SOURCE_WEIGHTS.get(article.source, 0.5)
        score = 1.0 + base_source_weight

        topic_scores = [
            weight
            for phrases, weight in _TOPIC_WEIGHTS
            if any(phrase in text for phrase in phrases)
        ]
        if topic_scores:
            score += max(topic_scores)
            score += min(sum(sorted(topic_scores, reverse=True)[1:]), 1.5)

        entity_score = sum(
            weight for entity, weight in _ENTITY_WEIGHTS if entity in text
        )
        score += min(entity_score, 2.4)

        if any(action in text for action in _MAJOR_ACTIONS):
            score += 0.8
        if any(phrase in text for phrase in _LOW_QUALITY_PHRASES):
            score -= 2.5
        if article.title.endswith("?"):
            score -= 0.5

        if article.published_at is not None:
            age_hours = max(
                (reference - article.published_at).total_seconds() / 3600,
                0.0,
            )
            score += max(0.0, 1.0 - age_hours / 24.0)

        return round(max(0.0, min(10.0, score)), 2)

    def rank_news(
        self, articles: list[NewsArticle], *, now: datetime | None = None
    ) -> list[NewsArticle]:
        """Return copies of articles ordered by descending importance and recency."""

        scored = [
            article.model_copy(
                update={"importance_score": self.score_article(article, now=now)}
            )
            for article in articles
        ]
        return sorted(
            scored,
            key=lambda article: (
                article.importance_score,
                article.published_at or datetime.min.replace(tzinfo=timezone.utc),
                article.title,
            ),
            reverse=True,
        )
