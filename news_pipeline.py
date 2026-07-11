"""Small shared helpers for news processing cycles."""

from __future__ import annotations

import logging
from typing import Iterable

from rss import NewsItem

logger = logging.getLogger(__name__)


def limit_candidates(items: Iterable[NewsItem], max_candidates: int) -> list[NewsItem]:
    """Keep one cycle bounded while preserving newest-first RSS ordering."""
    item_list = list(items)
    if max_candidates <= 0 or len(item_list) <= max_candidates:
        return item_list

    logger.info(
        "Limiting AI relevance candidates from %s to %s for this cycle.",
        len(item_list),
        max_candidates,
    )
    return item_list[:max_candidates]
