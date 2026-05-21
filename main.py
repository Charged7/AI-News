from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from ai import AISummaryError, AiNewsText, summarize_news_items
from config import NEWS_LOOKBACK_HOURS, RSS_SOURCES, SCHEDULE_HOURS, SCHEDULE_TIMEZONE, SENT_NEWS_PATH, SENT_NEWS_RETENTION_DAYS
from rss import NewsItem, fetch_recent_news
from sent_news import SentNewsStore
from telegram import TelegramClient, build_news_message

logger = logging.getLogger(__name__)


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    configure_output()

    parser = argparse.ArgumentParser(description="Send a daily Telegram RSS news feed.")
    parser.add_argument("--dry-run", action="store_true", help="Print messages without calling Telegram API.")
    parser.add_argument("--scheduled", action="store_true", help="Send only when local schedule hour matches.")
    parser.add_argument("--lookback-hours", type=int, default=NEWS_LOOKBACK_HOURS)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if args.scheduled and not should_run_scheduled():
        logger.info("Not the scheduled Kyiv hour; skipping send.")
        return 0

    try:
        items = fetch_recent_news(RSS_SOURCES, lookback_hours=args.lookback_hours)
    except Exception:
        logger.exception("RSS fetching failed.")
        return 1

    sent_store = SentNewsStore.load(SENT_NEWS_PATH, SENT_NEWS_RETENTION_DAYS)
    items = sent_store.filter_unsent(items)
    if not items:
        logger.info("No new news items to send.")
        return 0

    try:
        summaries = summarize_news_items(items)
    except AISummaryError:
        logger.exception("AI summary generation failed.")
        return 1

    if args.dry_run:
        print_dry_run(items, summaries)
        return 0

    sent_items: list[NewsItem] = []
    try:
        client = TelegramClient()
        for index, item in enumerate(items, start=1):
            client.send_news_item(index, item, summaries[item.link])
            sent_items.append(item)
    except Exception:
        if sent_items:
            sent_store.mark_sent(sent_items)
            sent_store.prune()
            sent_store.save()
        logger.exception("Telegram sending failed.")
        return 1

    sent_store.mark_sent(items)
    sent_store.prune()
    sent_store.save()
    logger.info("Sent %s news item(s).", len(items))
    return 0


def should_run_scheduled(now: datetime | None = None) -> bool:
    timezone = ZoneInfo(SCHEDULE_TIMEZONE)
    local_now = (now or datetime.now(timezone)).astimezone(timezone)
    return local_now.hour in SCHEDULE_HOURS


def print_dry_run(items: list[NewsItem], summaries: dict[str, AiNewsText]) -> None:
    for index, item in enumerate(items, start=1):
        if not item.image:
            raise ValueError(f"Image URL is required for news item: {item.link}")
        print(f"[PHOTO] {item.image}")
        print(build_news_message(index, item, summaries[item.link]))
        print()


if __name__ == "__main__":
    raise SystemExit(main())
