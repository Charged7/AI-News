"""Long-running VPS bot loop for near-real-time important news delivery."""

from __future__ import annotations

import logging
import sys
import time

from ai import AISummaryError, summarize_news_items
from config import (
    NEWS_LOOKBACK_HOURS,
    NEWS_MAX_CANDIDATES_PER_RUN,
    NEWS_MAX_ITEMS_PER_RUN,
    NEWS_MIN_IMPACT_SCORE,
    NEWS_POLL_INTERVAL_SECONDS,
    NEWS_STATE_DB_PATH,
    RSS_SOURCES,
    SENT_NEWS_PATH,
    SENT_NEWS_RETENTION_DAYS,
    PROCESSED_NEWS_PATH,
)
from impact_ai import ImpactClassificationError, select_important_news
from news_pipeline import limit_candidates
from news_state import NewsStateStore
from rss import NewsItem, fetch_recent_news
from telegram import TelegramClient

logger = logging.getLogger(__name__)


def configure_output() -> None:
    """Force UTF-8 output for readable Ukrainian logs."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def run_news_cycle(client: TelegramClient | None = None) -> int:
    """Fetch, classify, summarize, and send newly important items once."""
    items = fetch_recent_news(RSS_SOURCES, lookback_hours=NEWS_LOOKBACK_HOURS)
    state_store = NewsStateStore.load(
        NEWS_STATE_DB_PATH,
        SENT_NEWS_RETENTION_DAYS,
        sent_legacy_path=SENT_NEWS_PATH,
        processed_legacy_path=PROCESSED_NEWS_PATH,
    )
    try:
        candidates = state_store.filter_unsent(items)
        if not candidates:
            logger.info("No new news items to classify.")
            return 0

        candidates = state_store.filter_unprocessed(candidates)
        if not candidates:
            logger.info("No new unclassified news items.")
            return 0
        candidates = limit_candidates(candidates, NEWS_MAX_CANDIDATES_PER_RUN)

        important_items = select_important_news(
            candidates,
            min_score=NEWS_MIN_IMPACT_SCORE,
            max_items=NEWS_MAX_ITEMS_PER_RUN,
        )
        if not important_items:
            state_store.mark_processed(candidates)
            state_store.prune()
            logger.info("No high-impact news items to send.")
            return 0

        summaries = summarize_news_items(important_items)
        telegram_client = client or TelegramClient()
        sent_count = 0

        for item in important_items:
            _send_one_item(telegram_client, state_store, item, summaries[item.link.strip().lower()])
            sent_count += 1

        state_store.mark_processed(candidates)
        state_store.prune()

        logger.info("Sent %s high-impact news item(s).", sent_count)
        return sent_count
    finally:
        state_store.close()


def run_forever(poll_interval_seconds: int = NEWS_POLL_INTERVAL_SECONDS) -> int:
    """Run frequent RSS polling until the process is stopped."""
    if poll_interval_seconds < 30:
        raise ValueError("NEWS_POLL_INTERVAL_SECONDS must be at least 30.")

    client = TelegramClient()
    logger.info("Charged News bot started. Poll interval: %s seconds.", poll_interval_seconds)

    while True:
        try:
            run_news_cycle(client)
        except (AISummaryError, ImpactClassificationError):
            logger.exception("AI processing failed; next cycle will retry.")
        except Exception:
            logger.exception("News cycle failed; next cycle will retry.")

        time.sleep(poll_interval_seconds)


def _send_one_item(
    client: TelegramClient,
    state_store: NewsStateStore,
    item: NewsItem,
    summary: object,
) -> None:
    """Send and persist one item immediately after successful delivery."""
    client.send_news_item(item, summary)
    state_store.mark_sent([item])
    state_store.prune()


def main() -> int:
    configure_output()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    try:
        return run_forever()
    except KeyboardInterrupt:
        logger.info("Charged News bot stopped by user.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
