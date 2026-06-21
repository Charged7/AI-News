"""Manual one-shot entry point: RSS -> AI impact -> AI summary -> Telegram."""

import logging
import sys

from ai import AISummaryError, summarize_news_items
from config import (
    NEWS_LOOKBACK_HOURS,
    NEWS_MAX_CANDIDATES_PER_RUN,
    NEWS_MAX_ITEMS_PER_RUN,
    NEWS_MIN_IMPACT_SCORE,
    NEWS_STATE_DB_PATH,
    RSS_SOURCES,
    SENT_NEWS_PATH,
    SENT_NEWS_RETENTION_DAYS,
    PROCESSED_NEWS_PATH,
)
from impact_ai import ImpactClassificationError, select_important_news
from news_dedup import (
    NEWS_STORY_DEDUPE_HOURS,
    NEWS_STORY_DEDUPE_THRESHOLD,
    filter_duplicate_story_items,
    link_key,
)
from news_pipeline import limit_candidates
from news_state import NewsStateStore
from rss import fetch_recent_news
from telegram import TelegramClient

logger = logging.getLogger(__name__)


def configure_output() -> None:
    """Force UTF-8 output for readable Ukrainian logs."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    """Run one complete manual news cycle."""
    configure_output()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        items = fetch_recent_news(RSS_SOURCES, lookback_hours=NEWS_LOOKBACK_HOURS)
    except Exception:
        logger.exception("RSS fetching failed.")
        return 1

    state_store = NewsStateStore.load(
        NEWS_STATE_DB_PATH,
        SENT_NEWS_RETENTION_DAYS,
        sent_legacy_path=SENT_NEWS_PATH,
        processed_legacy_path=PROCESSED_NEWS_PATH,
    )
    try:
        items = state_store.filter_unsent(items)
        if not items:
            logger.info("No new news items to send.")
            return 0

        candidates = state_store.filter_unprocessed(items)
        if not candidates:
            logger.info("No new unclassified news items.")
            return 0
        candidates = limit_candidates(candidates, NEWS_MAX_CANDIDATES_PER_RUN)

        try:
            items = select_important_news(
                candidates,
                min_score=NEWS_MIN_IMPACT_SCORE,
                max_items=NEWS_MAX_ITEMS_PER_RUN,
            )
        except ImpactClassificationError:
            logger.exception("AI impact classification failed.")
            return 1

        if not items:
            state_store.mark_processed(candidates)
            state_store.prune()
            logger.info("No high-impact news items to send.")
            return 0

        client = TelegramClient()
        try:
            summaries = summarize_news_items(items)
            deduplication = filter_duplicate_story_items(
                items,
                summaries,
                existing_fingerprints=state_store.recent_story_fingerprints(
                    hours=NEWS_STORY_DEDUPE_HOURS
                ),
                threshold=NEWS_STORY_DEDUPE_THRESHOLD,
            )
            items = deduplication.unique_items
            for duplicate_item in deduplication.duplicate_items:
                logger.info("Skipping duplicate story from %s: %s", duplicate_item.source, duplicate_item.title)

            if not items:
                state_store.mark_processed(candidates)
                state_store.prune()
                logger.info("No new high-impact stories to send after deduplication.")
                return 0

            for item in items:
                client.send_news_item(item, summaries[link_key(item.link)])
                state_store.mark_sent([item], summaries={link_key(item.link): summaries[link_key(item.link)]})
                state_store.prune()
        except AISummaryError:
            logger.exception("AI summary generation failed.")
            return 1
        except Exception:
            logger.exception("Telegram sending failed.")
            return 1

        state_store.mark_processed(candidates)
        state_store.prune()

        logger.info("Sent %s news item(s).", len(items))
        return 0
    finally:
        state_store.close()


if __name__ == "__main__":
    raise SystemExit(main())
