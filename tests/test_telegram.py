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

    def test_send_news_item_requires_image(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")
        client = TelegramClient(TelegramSettings(bot_token="token", chat_id="chat"))

        with self.assertRaises(ValueError):
            client.send_news_item(1, item, "Короткий опис.")


if __name__ == "__main__":
    unittest.main()
