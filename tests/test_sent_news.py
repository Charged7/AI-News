"""Тести для JSON-сховища вже відправлених новин."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rss import NewsItem
from sent_news import SentNewsStore


class SentNewsStoreTests(unittest.TestCase):
    """Перевіряє збереження, завантаження та очищення history-файлу."""

    def test_filter_unsent_removes_previously_sent_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sent_news.json"
            item = NewsItem("Title", "Desc", "https://example.test/a", "https://image.test/a.jpg", "Source")
            store = SentNewsStore.load(path, retention_days=30)
            store.mark_sent([item], now=datetime(2026, 5, 21, 9, 0, tzinfo=UTC))

            self.assertEqual(store.filter_unsent([item]), [])

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sent_news.json"
            item = NewsItem("Title", "Desc", "https://example.test/a", "https://image.test/a.jpg", "Source")
            store = SentNewsStore.load(path, retention_days=30)
            store.mark_sent([item], now=datetime(2026, 5, 21, 9, 0, tzinfo=UTC))
            store.save()

            loaded = SentNewsStore.load(path, retention_days=30)

            self.assertEqual(loaded.filter_unsent([item]), [])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["items"][0]["link"], item.link)

    def test_prune_removes_old_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sent_news.json"
            old_item = NewsItem("Old", "Desc", "https://example.test/old", "https://image.test/old.jpg", "Source")
            new_item = NewsItem("New", "Desc", "https://example.test/new", "https://image.test/new.jpg", "Source")
            now = datetime(2026, 5, 21, 9, 0, tzinfo=UTC)
            store = SentNewsStore.load(path, retention_days=14)
            store.mark_sent([old_item], now=now - timedelta(days=20))
            store.mark_sent([new_item], now=now)
            store.prune(now=now)

            self.assertEqual(store.filter_unsent([old_item, new_item]), [old_item])


if __name__ == "__main__":
    unittest.main()
