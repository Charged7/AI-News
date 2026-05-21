from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from ai import AISummaryError, summarize_news_items
from config import NEWS_LOOKBACK_HOURS, RSS_SOURCES, SCHEDULE_HOURS, SCHEDULE_TIMEZONE
from rss import NewsItem, fetch_recent_news
from telegram import TelegramClient, build_intro_message, build_news_message, should_use_photo

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
    parser.add_argument("--no-ai", action="store_true", help="Use local fallback summaries even when OPENAI_API_KEY is set.")
    parser.add_argument("--require-ai", action="store_true", help="Fail instead of using fallback summaries if AI is unavailable.")
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

    try:
        summaries = summarize_news_items(items, use_ai=not args.no_ai, require_ai=args.require_ai)
    except AISummaryError:
        logger.exception("AI summaries are required, but generation failed.")
        return 1

    if args.dry_run:
        print_dry_run(items, summaries)
        return 0

    try:
        client = TelegramClient()
        client.send_message(build_intro_message(items))
        for index, item in enumerate(items, start=1):
            client.send_news_item(index, item, summaries.get(item.link, "Короткий опис недоступний."))
    except Exception:
        logger.exception("Telegram sending failed.")
        return 1

    logger.info("Sent %s news item(s).", len(items))
    return 0


def should_run_scheduled(now: datetime | None = None) -> bool:
    timezone = ZoneInfo(SCHEDULE_TIMEZONE)
    local_now = (now or datetime.now(timezone)).astimezone(timezone)
    return local_now.hour in SCHEDULE_HOURS


def print_dry_run(items: list[NewsItem], summaries: dict[str, str]) -> None:
    print(build_intro_message(items))
    print()
    for index, item in enumerate(items, start=1):
        if should_use_photo(item):
            print(f"[PHOTO] {item.image}")
        print(build_news_message(index, item, summaries.get(item.link, "Короткий опис недоступний.")))
        print()


if __name__ == "__main__":
    raise SystemExit(main())
