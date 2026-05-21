from __future__ import annotations
import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at runtime
    load_dotenv = None

if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class RSSSource:
    name: str
    url: str


RSS_SOURCES: list[RSSSource] = [
    RSSSource(name="The Verge", url="https://www.theverge.com/rss/index.xml"),
    RSSSource(name="Engadget", url="https://www.engadget.com/rss.xml"),
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_REQUEST_DELAY_SECONDS = float(os.getenv("OPENAI_REQUEST_DELAY_SECONDS", "1"))
OPENAI_RATE_LIMIT_RETRIES = int(os.getenv("OPENAI_RATE_LIMIT_RETRIES", "3"))

NEWS_LOOKBACK_HOURS = int(os.getenv("NEWS_LOOKBACK_HOURS", "6"))
SENT_NEWS_PATH = os.getenv("SENT_NEWS_PATH", "data/sent_news.json")
SENT_NEWS_RETENTION_DAYS = int(os.getenv("SENT_NEWS_RETENTION_DAYS", "30"))
