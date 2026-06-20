"""Tests for the long-running bot cycle helpers."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ai import AiNewsText
from bot import run_news_cycle
from rss import NewsItem


class FakeStateStore:
    def __init__(self, items: list[NewsItem]) -> None:
        self.items = items
        self.sent: list[NewsItem] = []
        self.processed: list[NewsItem] = []

    def filter_unsent(self, items: list[NewsItem]) -> list[NewsItem]:
        return items

    def filter_unprocessed(self, items: list[NewsItem]) -> list[NewsItem]:
        return items

    def mark_sent(self, items: list[NewsItem]) -> None:
        self.sent.extend(items)

    def mark_processed(self, items: list[NewsItem]) -> None:
        self.processed.extend(items)

    def prune(self) -> None:
        return None

    def close(self) -> None:
        return None


class BotTests(unittest.TestCase):
    def test_run_news_cycle_sends_and_persists_each_item(self) -> None:
        item = NewsItem("Major event", "Important text", "https://event.test", None, "Reuters")
        store = FakeStateStore([item])
        client = MagicMock()

        with (
            patch("bot.fetch_recent_news", return_value=[item]),
            patch("bot.NewsStateStore.load", return_value=store),
            patch("bot.select_important_news", return_value=[item]),
            patch("bot.summarize_news_items", return_value={"https://event.test": AiNewsText("Title", "Summary")}),
        ):
            sent_count = run_news_cycle(client)

        self.assertEqual(sent_count, 1)
        client.send_news_item.assert_called_once_with(item, AiNewsText("Title", "Summary"))
        self.assertEqual(store.sent, [item])
        self.assertEqual(store.processed, [item])


if __name__ == "__main__":
    unittest.main()
