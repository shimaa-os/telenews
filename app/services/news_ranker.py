"""Transparent deterministic importance scoring for AI news."""

from datetime import datetime, timezone

from app.models.news import NewsArticle


_TOPIC_WEIGHTS: tuple[tuple[tuple[str, ...], float], ...] = (
    (("foundation model", "frontier model", "large language model", " llm"), 3.5),
    (("model release", "new model", "launches model", "releases model"), 3.0),
    (("ai agent", "agentic ai", "multi-agent", "agent sdk"), 2.8),
    (("benchmark", "research", "paper", "transformer"), 1.8),
    (("ai safety", "alignment", "red teaming", "model safety"), 1.8),
    (("regulation", "ai act", "legislation", "executive order"), 2.0),
    (("acquisition", "acquires", "partnership", "partners with"), 1.6),
    (("developer", " api", "sdk", "open source", "fine-tuning", " rag"), 1.5),
)

_ENTITY_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("openai", 1.7),
    ("anthropic", 1.6),
    ("hugging face", 1.2),
    ("claude", 1.5),
    ("deepmind", 1.5),
    ("gemini", 1.5),
    ("microsoft", 1.1),
    ("nvidia", 1.1),
)

_SOURCE_WEIGHTS = {
    "OpenAI": 1.3,
    "Hugging Face": 1.2,
    "Google DeepMind": 1.3,
    "Google AI": 1.2,
    "Microsoft AI": 1.2,
    "NVIDIA AI": 1.2,
    "MIT Technology Review": 1.1,
    "Ars Technica": 1.0,
    "TechCrunch AI": 0.9,
    "The Verge AI": 0.9,
}

_LOW_QUALITY_PHRASES = (
    "opinion:",
    "sponsored",
    "you won't believe",
    "what you need to know",
    "best ai tools",
    "top 10",
    "deal",
    "sale",
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
        score = 1.0 + _SOURCE_WEIGHTS.get(article.source, 0.5)

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
