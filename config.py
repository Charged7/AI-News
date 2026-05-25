"""Централізовані налаштування бота та завантаження змінних середовища."""

from __future__ import annotations
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at runtime
    load_dotenv = None

if load_dotenv:
    # Локально підтягуємо значення з .env, щоб не вводити їх вручну щоразу.
    load_dotenv()


@dataclass(frozen=True)
class RSSSource:
    name: str
    url: str


# Публічні RSS-джерела, з яких бот збирає новини.
RSS_SOURCES: list[RSSSource] = [
    RSSSource(name="The Verge", url="https://www.theverge.com/rss/index.xml"),
    RSSSource(name="Engadget", url="https://www.engadget.com/rss.xml"),
    RSSSource(name="9to5Mac", url="https://9to5mac.com/feed/"),
    RSSSource(name="AppleInsider News", url="https://appleinsider.com/rss/news/"),
    RSSSource(name="TechCrunch", url="https://techcrunch.com/feed/"),
]

# Доступ до Telegram-бота і цільового чату.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Параметри OpenAI для batch-підсумків новин.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_RATE_LIMIT_RETRIES = int(os.getenv("OPENAI_RATE_LIMIT_RETRIES", "3"))

# Межі вибірки та збереження історії відправок.
NEWS_LOOKBACK_HOURS = int(os.getenv("NEWS_LOOKBACK_HOURS", "24"))
SENT_NEWS_PATH = os.getenv("SENT_NEWS_PATH", "data/sent_news.json")
SENT_NEWS_RETENTION_DAYS = int(os.getenv("SENT_NEWS_RETENTION_DAYS", "30"))
