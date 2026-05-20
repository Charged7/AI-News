from __future__ import annotations

import unittest
from datetime import UTC, datetime

from rss import NewsItem
from telegram import build_intro_message, build_news_message, should_use_photo


class TelegramTests(unittest.TestCase):
    def test_should_use_photo_only_when_image_exists(self) -> None:
        with_image = NewsItem("Title", "Desc", "https://example.test", "https://image.test/a.jpg", "The Verge")
        without_image = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")

        self.assertTrue(should_use_photo(with_image))
        self.assertFalse(should_use_photo(without_image))

    def test_build_news_message_contains_source_summary_and_link(self) -> None:
        item = NewsItem("Title", "Desc", "https://example.test", None, "The Verge")
        message = build_news_message(1, item, "Короткий опис.")

        self.assertIn("📰 1. Title (The Verge)", message)
        self.assertIn("Короткий опис.", message)
        self.assertIn("🔗 https://example.test", message)

    def test_build_intro_message_keeps_previous_format_without_dates(self) -> None:
        items = [
            NewsItem("A", "Desc", "https://a.test", None, "The Verge"),
            NewsItem("B", "Desc", "https://b.test", None, "The Verge"),
        ]

        self.assertEqual(build_intro_message(items), "🌍 Ранкова стрічка новин\n2 новини за останні 24 години з The Verge.")

    def test_build_intro_message_shows_single_news_date(self) -> None:
        items = [
            NewsItem("A", "Desc", "https://a.test", None, "The Verge", datetime(2026, 5, 20, 6, 0, tzinfo=UTC)),
            NewsItem("B", "Desc", "https://b.test", None, "The Verge", datetime(2026, 5, 20, 7, 0, tzinfo=UTC)),
        ]

        self.assertEqual(
            build_intro_message(items),
            "🌍 Ранкова стрічка новин\n20 травня 2026\n2 новини за останні 24 години з The Verge.",
        )

    def test_build_intro_message_shows_news_date_range(self) -> None:
        items = [
            NewsItem("A", "Desc", "https://a.test", None, "The Verge", datetime(2026, 5, 19, 18, 0, tzinfo=UTC)),
            NewsItem("B", "Desc", "https://b.test", None, "The Verge", datetime(2026, 5, 20, 7, 0, tzinfo=UTC)),
        ]

        self.assertEqual(
            build_intro_message(items),
            "🌍 Ранкова стрічка новин\n19-20 травня 2026\n2 новини за останні 24 години з The Verge.",
        )


if __name__ == "__main__":
    unittest.main()
