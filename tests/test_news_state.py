"""Tests for SQLite-backed news state."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from news_state import NewsStateStore
from rss import NewsItem


class NewsStateTests(unittest.TestCase):
    def test_sent_and_processed_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            item = NewsItem("Title", "Text", "https://example.test", None, "Source")
            store = NewsStateStore.load(db_path, retention_days=30)
            store.mark_sent([item], now=datetime(2026, 6, 20, 10, 0, tzinfo=UTC))
            store.mark_processed([item], now=datetime(2026, 6, 20, 10, 0, tzinfo=UTC))
            store.close()

            loaded = NewsStateStore.load(db_path, retention_days=30)
            try:
                self.assertEqual(loaded.filter_unsent([item]), [])
                self.assertEqual(loaded.filter_unprocessed([item]), [])
            finally:
                loaded.close()

    def test_sent_items_store_recent_story_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            item = NewsItem(
                "Vance arrives in Switzerland for US-Iran talks",
                "Both nations seek a deal.",
                "https://example.test/vance-switzerland-iran-talks",
                None,
                "Source",
            )
            store = NewsStateStore.load(db_path, retention_days=30)
            try:
                store.mark_sent([item], now=datetime(2026, 6, 20, 10, 0, tzinfo=UTC))
                fingerprints = store.recent_story_fingerprints(
                    hours=24,
                    now=datetime(2026, 6, 20, 11, 0, tzinfo=UTC),
                )

                self.assertEqual(len(fingerprints), 1)
                self.assertIn("vance", fingerprints[0])
                self.assertIn("iran", fingerprints[0])
            finally:
                store.close()

    def test_recent_story_fingerprints_respect_hours_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            item = NewsItem("Old event", "Text", "https://old.test/event", None, "Source")
            now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
            store = NewsStateStore.load(db_path, retention_days=30)
            try:
                store.mark_sent([item], now=now - timedelta(hours=48))

                self.assertEqual(store.recent_story_fingerprints(hours=24, now=now), [])
            finally:
                store.close()

    def test_prune_removes_old_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            old_item = NewsItem("Old", "Text", "https://old.test", None, "Source")
            new_item = NewsItem("New", "Text", "https://new.test", None, "Source")
            now = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
            store = NewsStateStore.load(db_path, retention_days=14)
            try:
                store.mark_sent([old_item], now=now - timedelta(days=30))
                store.mark_sent([new_item], now=now)
                store.prune(now=now)

                self.assertEqual(store.filter_unsent([old_item, new_item]), [old_item])
            finally:
                store.close()

    def test_imports_legacy_sent_json_when_database_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            legacy_path = Path(temp_dir) / "sent_news.json"
            item = NewsItem("Title", "Text", "https://legacy.test", None, "Source")
            legacy_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "link": item.link,
                                "title": item.title,
                                "source": item.source,
                                "sent_at": "2026-06-20T10:00:00+00:00",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            store = NewsStateStore.load(
                db_path,
                retention_days=30,
                sent_legacy_path=legacy_path,
            )
            try:
                self.assertEqual(store.filter_unsent([item]), [])
            finally:
                store.close()

    def test_imports_legacy_processed_json_when_database_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            legacy_path = Path(temp_dir) / "processed_news.json"
            item = NewsItem("Title", "Text", "https://processed.test", None, "Source")
            legacy_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "link": item.link,
                                "title": item.title,
                                "source": item.source,
                                "processed_at": "2026-06-20T10:00:00+00:00",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            store = NewsStateStore.load(
                db_path,
                retention_days=30,
                processed_legacy_path=legacy_path,
            )
            try:
                self.assertEqual(store.filter_unprocessed([item]), [])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
