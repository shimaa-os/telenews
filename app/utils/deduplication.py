"""URL and fuzzy-title duplicate removal."""

from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models.news import NewsArticle
from app.utils.text_utils import normalize_title


_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def canonicalize_url(url: str) -> str:
    """Remove fragments and common tracking parameters from an article URL."""

    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_KEYS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), path, urlencode(query), "")
    )


def title_similarity(left: str, right: str) -> float:
    """Return a similarity score that combines phrase and token overlap."""

    left_normalized = normalize_title(left)
    right_normalized = normalize_title(right)
    if not left_normalized or not right_normalized:
        return 0.0
    sequence_score = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    token_score = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    containment_score = len(left_tokens & right_tokens) / max(
        min(len(left_tokens), len(right_tokens)), 1
    )
    return max(sequence_score, token_score, containment_score)


def remove_duplicates(
    articles: list[NewsArticle], *, title_threshold: float = 0.84
) -> list[NewsArticle]:
    """Remove exact URL and near-title duplicates, keeping the richer article."""

    unique: list[NewsArticle] = []
    urls: set[str] = set()

    for article in articles:
        canonical_url = canonicalize_url(str(article.url))
        duplicate_index: int | None = None

        if canonical_url in urls:
            duplicate_index = next(
                index
                for index, existing in enumerate(unique)
                if canonicalize_url(str(existing.url)) == canonical_url
            )
        else:
            for index, existing in enumerate(unique):
                if title_similarity(article.title, existing.title) >= title_threshold:
                    duplicate_index = index
                    break

        if duplicate_index is None:
            unique.append(article)
            urls.add(canonical_url)
            continue

        if len(article.description) > len(unique[duplicate_index].description):
            old_url = canonicalize_url(str(unique[duplicate_index].url))
            unique[duplicate_index] = article
            urls.discard(old_url)
            urls.add(canonical_url)

    return unique
