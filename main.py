from __future__ import annotations

import argparse
import logging
import sys

from ai import AISummaryError, summarize_news_digest
from config import NEWS_LOOKBACK_HOURS, RSS_SOURCES, SENT_NEWS_PATH, SENT_NEWS_RETENTION_DAYS
from rss import fetch_recent_news
from sent_news import SentNewsStore
from telegram import TelegramClient, build_digest_message

logger = logging.getLogger(__name__)


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    configure_output()

    parser = argparse.ArgumentParser(description="Send an AI-generated Telegram news digest.")
    parser.add_argument("--lookback-hours", type=int, default=NEWS_LOOKBACK_HOURS)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

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

    client = TelegramClient()
    try:
        digest = summarize_news_digest(items)
        client.send_message(build_digest_message(digest.digest))
    except AISummaryError:
        logger.exception("AI digest generation failed.")
        return 1
    except Exception:
        logger.exception("Telegram sending failed.")
        return 1

    sent_store.mark_sent(items)
    sent_store.prune()
    sent_store.save()
    logger.info("Sent digest with %s news item(s).", len(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
