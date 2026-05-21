from __future__ import annotations

import unittest
from datetime import UTC, datetime

from rss import NewsItem
from telegram import TelegramClient, TelegramSettings, build_intro_message, build_news_message


class TelegramTests(unittest.TestCase):
    def test_build_news_message_contains_source_summary_and_link(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")
        message = build_news_message(1, item, "Короткий опис.")

        self.assertIn("📰 1. Title (The Verge)", message)
        self.assertIn("Короткий опис.", message)
        self.assertIn("🔗 https://example.test", message)

    def test_send_news_item_requires_image(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")
        client = TelegramClient(TelegramSettings(bot_token="token", chat_id="chat"))

        with self.assertRaises(ValueError):
            client.send_news_item(1, item, "Короткий опис.")

    def test_build_intro_message_keeps_previous_format_without_dates(self) -> None:
        items = [
            NewsItem("A", "Desc", "https://a.test", None, "The Verge"),
            NewsItem("B", "Desc", "https://b.test", None, "The Verge"),
        ]

        self.assertEqual(build_intro_message(items), "🌍 Ранкова стрічка новин\n2 новини за останні 12 годин з The Verge.")

    def test_build_intro_message_shows_single_news_date(self) -> None:
        items = [
            NewsItem("A", "Desc", "https://a.test", None, "The Verge", datetime(2026, 5, 20, 6, 0, tzinfo=UTC)),
            NewsItem("B", "Desc", "https://b.test", None, "The Verge", datetime(2026, 5, 20, 7, 0, tzinfo=UTC)),
        ]

        self.assertEqual(
            build_intro_message(items),
            "🌍 Ранкова стрічка новин\n20 травня 2026\n2 новини за останні 12 годин з The Verge.",
        )

    def test_build_intro_message_shows_news_date_range(self) -> None:
        items = [
            NewsItem("A", "Desc", "https://a.test", None, "The Verge", datetime(2026, 5, 19, 18, 0, tzinfo=UTC)),
            NewsItem("B", "Desc", "https://b.test", None, "The Verge", datetime(2026, 5, 20, 7, 0, tzinfo=UTC)),
        ]

        self.assertEqual(
            build_intro_message(items),
            "🌍 Ранкова стрічка новин\n19-20 травня 2026\n2 новини за останні 12 годин з The Verge.",
        )


if __name__ == "__main__":
    unittest.main()
