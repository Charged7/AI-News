"""Точка входу: збирає RSS, формує картки новин і надсилає їх у Telegram."""

import logging
import sys

from ai import AISummaryError, summarize_news_items
from config import NEWS_LOOKBACK_HOURS, RSS_SOURCES, SENT_NEWS_PATH, SENT_NEWS_RETENTION_DAYS
from rss import fetch_recent_news
from sent_news import SentNewsStore
from telegram import TelegramClient

logger = logging.getLogger(__name__)


def configure_output() -> None:
    """Ставить UTF-8 для stdout/stderr, щоб український текст не ламався в логах."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> int:
    """Запускає повний цикл: RSS -> dedup -> batch AI -> Telegram cards -> history."""
    configure_output()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    try:
        items = fetch_recent_news(RSS_SOURCES, lookback_hours=NEWS_LOOKBACK_HOURS)
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
        # OpenAI отримує весь список новин одним batch-запитом і повертає: перекладений заголовок, короткий summary для кожної новини.
        summaries = summarize_news_items(items)
        for item in items:
            client.send_news_item(item, summaries[item.link.strip().lower()]) # надсилаємо в Telegram як картку.
    except AISummaryError:
        logger.exception("AI summary generation failed.")
        return 1
    except Exception:
        logger.exception("Telegram sending failed.")
        return 1

    # Якщо все успішно відправилось:

    # новини помічаються як надіслані
    sent_store.mark_sent(items)

    # старі записи чистяться
    sent_store.prune()

    # історія зберігається назад у файл
    sent_store.save()

    logger.info("Sent %s news item(s).", len(items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
