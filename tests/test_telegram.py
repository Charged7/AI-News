from __future__ import annotations

import unittest

from ai import AiNewsText
from rss import NewsItem
from telegram import TelegramClient, TelegramSettings, build_news_message


class TelegramTests(unittest.TestCase):
    def test_build_news_message_contains_source_summary_and_link(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")
        message = build_news_message(1, item, AiNewsText("Український заголовок", "Короткий опис."))

        self.assertIn("📰 <b>Український заголовок</b> (The Verge)", message)
        self.assertIn("</b> (The Verge)\n\nКороткий опис.", message)
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


if __name__ == "__main__":
    unittest.main()
