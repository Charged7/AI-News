from __future__ import annotations

from dataclasses import dataclass
from html import escape

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

TELEGRAM_MESSAGE_LIMIT = 4096


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

    def _post(self, method: str, payload: dict[str, str]) -> None:
        import requests

        url = f"https://api.telegram.org/bot{self.settings.bot_token}/{method}"
        response = requests.post(url, data=payload, timeout=30)
        if not response.ok:
            raise RuntimeError(f"Telegram {method} failed: {response.status_code} {response.text}")


def build_digest_message(digest: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    header = "🗞️ <b>Дайджест новин</b>\n\n"
    body = escape(digest.strip())
    return _truncate(f"{header}{body}", limit)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return f"{text[: limit - 3].rstrip()}..."
