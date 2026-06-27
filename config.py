"""Централізовані налаштування бота та завантаження змінних середовища."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

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
    category: str = "general"
    priority: str = "normal"


DEFAULT_RSS_SOURCES: list[RSSSource] = [
    RSSSource(name="The Verge", url="https://www.theverge.com/rss/index.xml"),
    RSSSource(name="Engadget", url="https://www.engadget.com/rss.xml"),
    RSSSource(name="9to5Mac", url="https://9to5mac.com/feed/"),
    RSSSource(name="AppleInsider News", url="https://appleinsider.com/rss/news/"),
    RSSSource(name="TechCrunch", url="https://techcrunch.com/feed/"),
]
NEWS_SOURCES_PATH = os.getenv("NEWS_SOURCES_PATH") or "data/rss_sources.json"


def _load_rss_sources(path: str | Path) -> list[RSSSource]:
    source_path = Path(path)
    if not source_path.exists():
        return DEFAULT_RSS_SOURCES

    data = json.loads(source_path.read_text(encoding="utf-8"))
    raw_sources = data.get("sources") if isinstance(data, dict) else data
    if not isinstance(raw_sources, list):
        raise ValueError(f"{source_path} must contain a JSON list or an object with a sources list.")

    sources: list[RSSSource] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict) or raw_source.get("enabled") is False:
            continue

        name = str(raw_source.get("name", "")).strip()
        url = str(raw_source.get("url", "")).strip()
        if not name or not url:
            continue

        sources.append(
            RSSSource(
                name=name,
                url=url,
                category=str(raw_source.get("category", "general")).strip() or "general",
                priority=str(raw_source.get("priority", "normal")).strip() or "normal",
            )
        )

    if not sources:
        raise ValueError(f"{source_path} does not contain any enabled RSS sources.")
    return sources


# Публічні RSS-джерела, з яких бот збирає новини.
RSS_SOURCES: list[RSSSource] = _load_rss_sources(NEWS_SOURCES_PATH)

# Доступ до Telegram-бота і цільового чату.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Параметри OpenAI для batch-підсумків новин.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
OPENAI_SUMMARY_BATCH_SIZE = _env_int("OPENAI_SUMMARY_BATCH_SIZE", 4)
OPENAI_SUMMARY_MAX_TOKENS = _env_int("OPENAI_SUMMARY_MAX_TOKENS", 4000)
OPENAI_IMPACT_BATCH_SIZE = _env_int("OPENAI_IMPACT_BATCH_SIZE", 6)
OPENAI_IMPACT_MAX_TOKENS = _env_int("OPENAI_IMPACT_MAX_TOKENS", 5000)
OPENAI_IMPACT_RETRY_MISSING_LIMIT = _env_int("OPENAI_IMPACT_RETRY_MISSING_LIMIT", 0)

# Межі вибірки та збереження історії відправок.
NEWS_LOOKBACK_HOURS = _env_int("NEWS_LOOKBACK_HOURS", 24)
NEWS_MIN_IMPACT_SCORE = _env_int("NEWS_MIN_IMPACT_SCORE", 75)
NEWS_MAX_CANDIDATES_PER_RUN = _env_int("NEWS_MAX_CANDIDATES_PER_RUN", 36)
NEWS_MAX_ITEMS_PER_RUN = _env_int("NEWS_MAX_ITEMS_PER_RUN", 0)
NEWS_POLL_INTERVAL_SECONDS = _env_int("NEWS_POLL_INTERVAL_SECONDS", 300)
NEWS_STATE_DB_PATH = os.getenv("NEWS_STATE_DB_PATH") or "data/newsbot.db"
PROCESSED_NEWS_PATH = os.getenv("PROCESSED_NEWS_PATH") or "data/processed_news.json"
SENT_NEWS_PATH = os.getenv("SENT_NEWS_PATH") or "data/sent_news.json"
SENT_NEWS_RETENTION_DAYS = _env_int("SENT_NEWS_RETENTION_DAYS", 30)
