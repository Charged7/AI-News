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
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_REQUEST_DELAY_SECONDS = float(os.getenv("OPENAI_REQUEST_DELAY_SECONDS", "21"))
OPENAI_RATE_LIMIT_RETRIES = int(os.getenv("OPENAI_RATE_LIMIT_RETRIES", "3"))

NEWS_LOOKBACK_HOURS = int(os.getenv("NEWS_LOOKBACK_HOURS", "24"))
SCHEDULE_TIMEZONE = os.getenv("SCHEDULE_TIMEZONE", "Europe/Kyiv")
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "9"))
