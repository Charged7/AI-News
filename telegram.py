from __future__ import annotations

import logging
from html import escape
from dataclasses import dataclass

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
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
        self._post(
            "sendMessage",
            {
                "chat_id": self.settings.chat_id,
                "text": _truncate(text, TELEGRAM_MESSAGE_LIMIT),
                "parse_mode": "HTML",
            },
        )

    def send_photo(self, photo_url: str, caption: str) -> None:
        self._post(
            "sendPhoto",
            {
                "chat_id": self.settings.chat_id,
                "photo": photo_url,
                "caption": _truncate(caption, TELEGRAM_CAPTION_LIMIT),
                "parse_mode": "HTML",
            },
        )

    def send_news_item(self, index: int, item: NewsItem, summary: object) -> None:
        if not item.image:
            raise ValueError(f"Image URL is required for news item: {item.link}")

        self.send_photo(item.image, build_news_message(index, item, summary, limit=TELEGRAM_CAPTION_LIMIT))

    def _post(self, method: str, payload: dict[str, str]) -> None:
        import requests

        url = f"https://api.telegram.org/bot{self.settings.bot_token}/{method}"
        response = requests.post(url, data=payload, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Telegram {method} failed: {response.status_code} {response.text}")


def build_news_message(index: int, item: NewsItem, summary: object, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    title = getattr(summary, "title", item.title)
    summary_text = getattr(summary, "summary", str(summary))
    prefix = f"📰 <b>{escape(str(title))}</b> ({escape(item.source)})\n\n"
    suffix = f"\n\n{escape(item.link)}"
    available_summary_length = max(40, limit - len(prefix) - len(suffix))
    summary_text = _truncate(str(summary_text).strip(), available_summary_length)
    return _truncate(f"{prefix}{escape(summary_text)}{suffix}", limit)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3].rstrip()}..."
