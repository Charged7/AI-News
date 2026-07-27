"""Tests for SQLite-backed news state."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from news_state import NewsStateStore
from relevance_ai import RelevanceDecision
from rss import NewsItem


class NewsStateTests(unittest.TestCase):
    def test_existing_database_is_migrated_with_personalization_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                """
                CREATE TABLE sent_news (
                    link TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL,
                    sent_at TEXT NOT NULL, story_fingerprint TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE processed_news (
                    link TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL,
                    processed_at TEXT NOT NULL
                )
                """
            )
            connection.close()

            store = NewsStateStore.load(db_path, retention_days=30)
            try:
                sent_columns = {
                    row[1]
                    for row in store.connection.execute("PRAGMA table_info(sent_news)")
                }
                processed_columns = {
                    row[1]
                    for row in store.connection.execute("PRAGMA table_info(processed_news)")
                }

                self.assertIn("relevance_score", sent_columns)
                self.assertIn("decision_reason", sent_columns)
                self.assertIn("profile_key", processed_columns)
            finally:
                store.close()

    def test_sent_and_processed_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            item = NewsItem("Title", "Text", "https://example.test", None, "Source")
            now = datetime.now(UTC)
            store = NewsStateStore.load(db_path, retention_days=30)
            store.mark_sent([item], now=now)
            store.mark_processed([item], now=now)
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

    def test_processed_state_is_scoped_to_preference_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            item = NewsItem("Title", "Text", "https://profile.test", None, "Source")
            store = NewsStateStore.load(db_path, retention_days=30)
            try:
                store.mark_processed([item], profile_key="profile-a")

                self.assertEqual(store.filter_unprocessed([item], profile_key="profile-a"), [])
                self.assertEqual(
                    store.filter_unprocessed([item], profile_key="profile-b"),
                    [item],
                )
            finally:
                store.close()

    def test_sent_state_persists_relevance_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "newsbot.db"
            item = NewsItem("Final", "Text", "https://metadata.test", None, "Source")
            decision = RelevanceDecision(
                item.link,
                True,
                92,
                80,
                ("football",),
                "sports",
                "final",
                "Фінал великого турніру.",
            )
            store = NewsStateStore.load(db_path, retention_days=30)
            try:
                store.mark_sent(
                    [item],
                    decisions={item.link: decision},
                    profile_key="profile-a",
                )
                row = store.connection.execute(
                    """
                    SELECT profile_key, relevance_score, importance_score,
                           matched_topics, decision_reason
                    FROM sent_news WHERE link = ?
                    """,
                    (item.link,),
                ).fetchone()

                self.assertEqual(row[0], "profile-a")
                self.assertEqual(row[1:3], (92, 80))
                self.assertEqual(json.loads(row[3]), ["football"])
                self.assertIn("Фінал", row[4])
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
            now = datetime.now(UTC)
            legacy_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "link": item.link,
                                "title": item.title,
                                "source": item.source,
                                "sent_at": now.isoformat(),
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
            now = datetime.now(UTC)
            legacy_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "link": item.link,
                                "title": item.title,
                                "source": item.source,
                                "processed_at": now.isoformat(),
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
