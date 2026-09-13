"""Safe text normalization helpers."""

import html
import re
import unicodedata


_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)

_TITLE_NOISE_WORDS = {
    "a",
    "an",
    "and",
    "announces",
    "announced",
    "for",
    "its",
    "latest",
    "launches",
    "new",
    "newest",
    "of",
    "releases",
    "released",
    "the",
    "to",
    "unveils",
    "with",
}


def clean_text(value: str | None, *, max_length: int = 8_000) -> str:
    """Convert untrusted HTML-ish feed text into compact plain text."""

    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text[:max_length]


def normalize_title(title: str) -> str:
    """Normalize a title for deterministic duplicate comparison."""

    normalized = unicodedata.normalize("NFKC", title).casefold()
    normalized = _NON_WORD_RE.sub(" ", normalized)
    words = [word for word in normalized.split() if word not in _TITLE_NOISE_WORDS]
    return " ".join(words)


def truncate(value: str, max_length: int) -> str:
    """Truncate at a word boundary and add an ellipsis when possible."""

    if len(value) <= max_length:
        return value
    shortened = value[: max_length - 1].rsplit(" ", 1)[0]
    return f"{shortened or value[: max_length - 1]}…"
