"""Тести для форматування і відправки Telegram-карток новин."""

from __future__ import annotations

import unittest

from ai import AiNewsText
from rss import NewsItem
from telegram import TelegramClient, TelegramSettings, build_news_message


class TelegramTests(unittest.TestCase):
    """Перевіряє HTML-формат і відправку карток у Telegram API."""

    def test_build_news_message_contains_source_summary_and_link(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")
        message = build_news_message(1, item, AiNewsText("Український заголовок", "Короткий опис."))

        self.assertIn("<b>Український заголовок</b> (The Verge)", message)
        self.assertNotIn("📰", message)
        self.assertIn("Короткий опис.", message)
        self.assertIn("https://example.test", message)

    def test_send_news_item_uses_message_without_image(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")
        client = TelegramClient(TelegramSettings(bot_token="token", chat_id="chat"))

        calls = []
        client._post = lambda method, payload: calls.append((method, payload))  # type: ignore[method-assign]

        client.send_news_item(1, item, AiNewsText("Український заголовок", "Короткий опис."))

        self.assertEqual(calls[0][0], "sendMessage")

    def test_send_news_item_uses_photo_with_image(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", "https://example.test/image.jpg", "The Verge")
        client = TelegramClient(TelegramSettings(bot_token="token", chat_id="chat"))

        calls = []
        client._post = lambda method, payload: calls.append((method, payload))  # type: ignore[method-assign]

        client.send_news_item(1, item, AiNewsText("Український заголовок", "Короткий опис."))

        self.assertEqual(calls[0][0], "sendPhoto")
        self.assertEqual(calls[0][1]["photo"], "https://example.test/image.jpg")

    def test_send_news_item_falls_back_to_message_if_photo_fails(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", "https://example.test/broken.jpg", "The Verge")
        client = TelegramClient(TelegramSettings(bot_token="token", chat_id="chat"))

        calls = []

        def fake_post(method: str, payload: dict[str, str]) -> None:
            calls.append((method, payload))
            if method == "sendPhoto":
                raise RuntimeError("bad photo")

        client._post = fake_post  # type: ignore[method-assign]

        client.send_news_item(1, item, AiNewsText("Український заголовок", "Короткий опис."))

        self.assertEqual(calls[0][0], "sendPhoto")
        self.assertEqual(calls[1][0], "sendMessage")


if __name__ == "__main__":
    unittest.main()
