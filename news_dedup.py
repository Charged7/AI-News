"""Story-level duplicate detection for news items from different sources."""

from __future__ import annotations

import re
import os
from dataclasses import dataclass
from typing import Iterable, Mapping
from urllib.parse import unquote, urlparse
from semantic_dedup import similarity

from rss import NewsItem, clean_text

DEFAULT_STORY_DEDUPE_THRESHOLD = 0.45
DEFAULT_STORY_DEDUPE_HOURS = 36
NEWS_STORY_DEDUPE_HOURS = int(os.getenv("NEWS_STORY_DEDUPE_HOURS") or DEFAULT_STORY_DEDUPE_HOURS)
NEWS_STORY_DEDUPE_THRESHOLD = float(
    os.getenv("NEWS_STORY_DEDUPE_THRESHOLD") or DEFAULT_STORY_DEDUPE_THRESHOLD
)
MIN_COMMON_STORY_TOKENS = 4
STRONG_COMMON_STORY_TOKENS = 5

_STOP_WORDS = {
    "about",
    "after",
    "against",
    "also",
    "amid",
    "and",
    "are",
    "but",
    "from",
    "for",
    "have",
    "into",
    "more",
    "news",
    "not",
    "over",
    "says",
    "that",
    "the",
    "their",
    "this",
    "with",
    "would",
    "www",
    "your",
    "article",
    "для",
    "або",
    "але",
    "без",
    "був",
    "була",
    "були",
    "буде",
    "від",
    "вже",
    "вони",
    "його",
    "над",
    "після",
    "про",
    "при",
    "та",
    "так",
    "що",
    "які",
    "який",
}


@dataclass(frozen=True)
class StoryDeduplicationResult:
    unique_items: list[NewsItem]
    duplicate_items: list[NewsItem]


def filter_duplicate_story_items(
    items: Iterable[NewsItem],
    summaries: Mapping[str, object],
    existing_fingerprints: Iterable[str] = (),
    threshold: float = NEWS_STORY_DEDUPE_THRESHOLD,
) -> StoryDeduplicationResult:
    """Keep only the first item for each story-like cluster."""
    seen = [fingerprint for fingerprint in existing_fingerprints if fingerprint.strip()]
    unique_items: list[NewsItem] = []
    duplicate_items: list[NewsItem] = []

    for item in items:
        fingerprint = build_story_fingerprint(item, summaries.get(link_key(item.link)))
        if is_similar_to_any_story(fingerprint, seen, threshold=threshold):
            duplicate_items.append(item)
            continue

        unique_items.append(item)
        if fingerprint:
            seen.append(fingerprint)

    return StoryDeduplicationResult(unique_items=unique_items, duplicate_items=duplicate_items)


def build_story_fingerprint(item: NewsItem, summary: object | None = None) -> str:
    """Build a comparable token fingerprint from AI text, RSS text, and URL slugs."""
    parts: list[str] = []
    if summary is not None:
        parts.append(str(getattr(summary, "title", "") or ""))
        parts.append(str(getattr(summary, "summary", "") or ""))
        parts.append(str(getattr(summary, "event_key", "") or ""))

    parts.extend([item.title, item.description, _link_text(item.link)])
    return " ".join(sorted(_tokenize_story_text(" ".join(parts))))


def is_similar_to_any_story(
    fingerprint: str,
    existing_fingerprints: Iterable[str],
    threshold: float = NEWS_STORY_DEDUPE_THRESHOLD,
) -> bool:
    return any(
        are_similar_stories(fingerprint, existing, threshold=threshold)
        for existing in existing_fingerprints
    )


def are_similar_stories(
    first_fingerprint: str,
    second_fingerprint: str,
    threshold: float = NEWS_STORY_DEDUPE_THRESHOLD,
) -> bool:

    first_tokens = set(first_fingerprint.split())
    second_tokens = set(second_fingerprint.split())

    if not first_tokens or not second_tokens:
        return False

    common_count = len(first_tokens & second_tokens)

    if common_count >= 5:
        return True

    semantic_score = similarity(
        first_fingerprint,
        second_fingerprint,
    )

    return semantic_score >= 0.88


def link_key(link: str) -> str:
    return link.strip().lower()


def _tokenize_story_text(text: str) -> set[str]:
    normalized = clean_text(text).lower()
    raw_tokens = re.findall(r"[a-z0-9а-яіїєґ]+", normalized, flags=re.IGNORECASE)
    return {
        token
        for token in raw_tokens
        if len(token) >= 3 and token not in _STOP_WORDS
    }


def _link_text(link: str) -> str:
    parsed = urlparse(link)
    return unquote(f"{parsed.netloc} {parsed.path} {parsed.query}").replace("/", " ")
