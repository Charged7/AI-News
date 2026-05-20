from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Iterable
from zoneinfo import ZoneInfo

from config import SCHEDULE_TIMEZONE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from rss import NewsItem

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = TELEGRAM_BOT_TOKEN
    chat_id: str = TELEGRAM_CHAT_ID


class TelegramClient:
    def __init__(self, settings: TelegramSettings | None = None) -> None:
        self.settings = settings or TelegramSettings()
        if not self.settings.bot_token or not self.settings.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required for sending.")

    def send_message(self, text: str) -> None:
        self._post("sendMessage", {"chat_id": self.settings.chat_id, "text": _truncate(text, TELEGRAM_MESSAGE_LIMIT)})

    def send_photo(self, photo_url: str, caption: str) -> None:
        self._post(
            "sendPhoto",
            {
                "chat_id": self.settings.chat_id,
                "photo": photo_url,
                "caption": _truncate(caption, TELEGRAM_CAPTION_LIMIT),
            },
        )

    def send_news_item(self, index: int, item: NewsItem, summary: str) -> None:
        if should_use_photo(item):
            try:
                self.send_photo(item.image or "", build_news_message(index, item, summary, limit=TELEGRAM_CAPTION_LIMIT))
                return
            except Exception as exc:
                logger.warning("sendPhoto failed for %s, falling back to sendMessage: %s", item.link, exc)

        self.send_message(build_news_message(index, item, summary, limit=TELEGRAM_MESSAGE_LIMIT))

    def _post(self, method: str, payload: dict[str, str]) -> None:
        import requests

        url = f"https://api.telegram.org/bot{self.settings.bot_token}/{method}"
        response = requests.post(url, data=payload, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Telegram {method} failed: {response.status_code} {response.text}")


def build_intro_message(items: Iterable[NewsItem]) -> str:
    items = list(items)
    count = len(items)
    sources = sorted({item.source for item in items})
    source_text = ", ".join(sources) if sources else "RSS"
    noun = _ukrainian_news_noun(count)
    date_text = _news_date_text(items)
    lines = ["🌍 Ранкова стрічка новин"]
    if date_text:
        lines.append(date_text)
    lines.append(f"{count} {noun} за останні 24 години з {source_text}.")
    return "\n".join(lines)


def build_news_message(index: int, item: NewsItem, summary: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    prefix = f"📰 {index}. {item.title} ({item.source})\n"
    suffix = f"\n\n🔗 {item.link}"
    available_summary_length = max(40, limit - len(prefix) - len(suffix))
    summary = _truncate(summary.strip(), available_summary_length)
    return _truncate(f"{prefix}{summary}{suffix}", limit)


def should_use_photo(item: NewsItem) -> bool:
    return bool(item.image)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3].rstrip()}..."


def _ukrainian_news_noun(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "новина"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "новини"
    return "новин"


def _news_date_text(items: list[NewsItem]) -> str | None:
    timezone = ZoneInfo(SCHEDULE_TIMEZONE)
    dates = sorted({
        item.published_at.astimezone(timezone).date()
        for item in items
        if item.published_at is not None
    })

    if not dates:
        return None
    if len(dates) == 1:
        return _format_ukrainian_date(dates[0])

    return _format_ukrainian_date_range(dates[0], dates[-1])


def _format_ukrainian_date_range(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start.day}-{_format_ukrainian_date(end)}"
    return f"{_format_ukrainian_date(start)} - {_format_ukrainian_date(end)}"


def _format_ukrainian_date(value: date) -> str:
    months = {
        1: "січня",
        2: "лютого",
        3: "березня",
        4: "квітня",
        5: "травня",
        6: "червня",
        7: "липня",
        8: "серпня",
        9: "вересня",
        10: "жовтня",
        11: "листопада",
        12: "грудня",
    }
    return f"{value.day} {months[value.month]} {value.year}"
