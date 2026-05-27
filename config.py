"""Централізовані налаштування бота та завантаження змінних середовища."""

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at runtime
    load_dotenv = None

if load_dotenv:
    # Локально підтягуємо значення з .env, щоб не вводити їх вручну щоразу.
    load_dotenv()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


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
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
OPENAI_SUMMARY_BATCH_SIZE = _env_int("OPENAI_SUMMARY_BATCH_SIZE", 8)
OPENAI_SUMMARY_MAX_TOKENS = _env_int("OPENAI_SUMMARY_MAX_TOKENS", 4000)

# Межі вибірки та збереження історії відправок.
NEWS_LOOKBACK_HOURS = _env_int("NEWS_LOOKBACK_HOURS", 24)
SENT_NEWS_PATH = os.getenv("SENT_NEWS_PATH", "data/sent_news.json")
SENT_NEWS_RETENTION_DAYS = _env_int("SENT_NEWS_RETENTION_DAYS", 30)
