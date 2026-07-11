"""SQLite-backed news state for sent and already-classified RSS links."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping

from news_dedup import build_story_fingerprint
from rss import NewsItem


@dataclass(frozen=True)
class NewsStateRecord:
    link: str
    title: str
    source: str
    timestamp: datetime


class NewsStateStore:
    """Stores delivery and classification state in one local SQLite database."""

    def __init__(self, path: str | Path, retention_days: int) -> None:
        self.path = Path(path)
        self.retention_days = retention_days
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._ensure_schema()

    @classmethod
    def load(
        cls,
        path: str | Path,
        retention_days: int,
        sent_legacy_path: str | Path | None = None,
        processed_legacy_path: str | Path | None = None,
    ) -> "NewsStateStore":
        """Open the state database and import legacy JSON state if needed."""
        store = cls(path, retention_days)
        if sent_legacy_path and not store._has_rows("sent_news"):
            store._import_legacy_json(sent_legacy_path, "sent_news", "sent_at")
        if processed_legacy_path and not store._has_rows("processed_news"):
            store._import_legacy_json(processed_legacy_path, "processed_news", "processed_at")
        store.prune()
        return store

    def filter_unsent(self, items: Iterable[NewsItem]) -> list[NewsItem]:
        return self._filter_missing(items, table="sent_news")

    def filter_unprocessed(
        self,
        items: Iterable[NewsItem],
        profile_key: str | None = None,
    ) -> list[NewsItem]:
        """Return items not yet classified for the active preference profile."""
        if profile_key is None:
            return self._filter_missing(items, table="processed_news")
        return [
            item
            for item in items
            if self.connection.execute(
                "SELECT 1 FROM processed_news WHERE link = ? AND profile_key = ?",
                (_link_key(item.link), profile_key),
            ).fetchone()
            is None
        ]

    def mark_sent(
        self,
        items: Iterable[NewsItem],
        now: datetime | None = None,
        summaries: Mapping[str, object] | None = None,
        decisions: Mapping[str, object] | None = None,
        profile_key: str | None = None,
    ) -> None:
        self._upsert_items(
            items,
            table="sent_news",
            timestamp_column="sent_at",
            now=now,
            summaries=summaries,
            decisions=decisions,
            profile_key=profile_key,
        )

    def mark_processed(
        self,
        items: Iterable[NewsItem],
        now: datetime | None = None,
        profile_key: str | None = None,
    ) -> None:
        self._upsert_items(
            items,
            table="processed_news",
            timestamp_column="processed_at",
            now=now,
            profile_key=profile_key,
        )

    def recent_story_fingerprints(
        self,
        hours: int | None = None,
        now: datetime | None = None,
    ) -> list[str]:
        """Return recent story fingerprints for cross-source duplicate suppression."""
        params: tuple[str, ...] = ()
        where_clause = ""
        if hours is not None and hours > 0:
            cutoff = (_as_utc(now or datetime.now(UTC)) - timedelta(hours=hours)).isoformat()
            where_clause = "WHERE sent_at >= ?"
            params = (cutoff,)

        rows = self.connection.execute(
            f"""
            SELECT link, title, source, story_fingerprint
            FROM sent_news
            {where_clause}
            """,
            params,
        ).fetchall()

        fingerprints: list[str] = []
        for link, title, source, story_fingerprint in rows:
            fingerprint = str(story_fingerprint or "").strip()
            if not fingerprint:
                fingerprint = build_story_fingerprint(
                    NewsItem(
                        title=str(title or ""),
                        description="",
                        link=str(link or ""),
                        image=None,
                        source=str(source or ""),
                    )
                )
            if fingerprint:
                fingerprints.append(fingerprint)
        return fingerprints

    def prune(self, now: datetime | None = None) -> None:
        cutoff = (_as_utc(now or datetime.now(UTC)) - timedelta(days=self.retention_days)).isoformat()
        with self.connection:
            self.connection.execute("DELETE FROM sent_news WHERE sent_at < ?", (cutoff,))
            self.connection.execute("DELETE FROM processed_news WHERE processed_at < ?", (cutoff,))

    def close(self) -> None:
        self.connection.close()

    def _ensure_schema(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_news (
                    link TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    story_fingerprint TEXT,
                    profile_key TEXT,
                    relevance_score INTEGER,
                    importance_score INTEGER,
                    matched_topics TEXT,
                    decision_reason TEXT
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_news (
                    link TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    profile_key TEXT
                )
                """
            )
            self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sent_news_sent_at ON sent_news(sent_at)"
            )
            self._ensure_column("sent_news", "story_fingerprint", "TEXT")
            self._ensure_column("sent_news", "profile_key", "TEXT")
            self._ensure_column("sent_news", "relevance_score", "INTEGER")
            self._ensure_column("sent_news", "importance_score", "INTEGER")
            self._ensure_column("sent_news", "matched_topics", "TEXT")
            self._ensure_column("sent_news", "decision_reason", "TEXT")
            self._ensure_column("processed_news", "profile_key", "TEXT")
            self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_news_processed_at ON processed_news(processed_at)"
            )

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {
            str(row[1])
            for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _filter_missing(self, items: Iterable[NewsItem], table: str) -> list[NewsItem]:
        return [
            item
            for item in items
            if self.connection.execute(
                f"SELECT 1 FROM {table} WHERE link = ?",
                (_link_key(item.link),),
            ).fetchone()
            is None
        ]

    def _upsert_items(
        self,
        items: Iterable[NewsItem],
        table: str,
        timestamp_column: str,
        now: datetime | None = None,
        summaries: Mapping[str, object] | None = None,
        decisions: Mapping[str, object] | None = None,
        profile_key: str | None = None,
    ) -> None:
        timestamp = _as_utc(now or datetime.now(UTC)).isoformat()
        item_list = list(items)
        rows = []
        for item in item_list:
            metadata = _decision_metadata(item, decisions)
            rows.append(
                (
                    _link_key(item.link),
                    item.title,
                    item.source,
                    timestamp,
                    build_story_fingerprint(item, _summary_for_item(item, summaries)),
                    profile_key,
                    metadata[0],
                    metadata[1],
                    metadata[2],
                    metadata[3],
                )
            )
        if not rows:
            return

        with self.connection:
            if table == "sent_news":
                self.connection.executemany(
                    f"""
                    INSERT INTO sent_news (
                        link, title, source, {timestamp_column}, story_fingerprint,
                        profile_key, relevance_score, importance_score,
                        matched_topics, decision_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        title = excluded.title,
                        source = excluded.source,
                        {timestamp_column} = excluded.{timestamp_column},
                        story_fingerprint = excluded.story_fingerprint,
                        profile_key = excluded.profile_key,
                        relevance_score = excluded.relevance_score,
                        importance_score = excluded.importance_score,
                        matched_topics = excluded.matched_topics,
                        decision_reason = excluded.decision_reason
                    """,
                    rows,
                )
            else:
                self.connection.executemany(
                    f"""
                    INSERT INTO {table} (link, title, source, {timestamp_column}, profile_key)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(link) DO UPDATE SET
                        title = excluded.title,
                        source = excluded.source,
                        {timestamp_column} = excluded.{timestamp_column},
                        profile_key = excluded.profile_key
                    """,
                    [(row[0], row[1], row[2], row[3], row[5]) for row in rows],
                )

    def _has_rows(self, table: str) -> bool:
        row = self.connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        return row is not None

    def _import_legacy_json(self, path: str | Path, table: str, timestamp_column: str) -> None:
        legacy_path = Path(path)
        if not legacy_path.exists():
            return

        data = json.loads(legacy_path.read_text(encoding="utf-8"))
        rows: list[tuple[str, str, str, str]] = []
        for raw_record in data.get("items", []):
            link = str(raw_record.get("link", "")).strip()
            timestamp = _parse_datetime(raw_record.get(timestamp_column))
            if not link or timestamp is None:
                continue
            rows.append(
                (
                    _link_key(link),
                    str(raw_record.get("title", "")).strip(),
                    str(raw_record.get("source", "")).strip(),
                    timestamp.isoformat(),
                )
            )

        if not rows:
            return

        with self.connection:
            self.connection.executemany(
                f"""
                INSERT OR IGNORE INTO {table} (link, title, source, {timestamp_column})
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )


def _link_key(link: str) -> str:
    return link.strip().lower()


def _summary_for_item(
    item: NewsItem,
    summaries: Mapping[str, object] | None,
) -> object | None:
    if not summaries:
        return None
    return summaries.get(_link_key(item.link))


def _decision_metadata(
    item: NewsItem,
    decisions: Mapping[str, object] | None,
) -> tuple[int | None, int | None, str | None, str | None]:
    if not decisions:
        return None, None, None, None
    decision = decisions.get(_link_key(item.link))
    if decision is None:
        return None, None, None, None

    relevance_score = getattr(decision, "relevance_score", None)
    importance_score = getattr(decision, "importance_score", None)
    topics = getattr(decision, "matched_topics", ())
    reason = str(getattr(decision, "reason_uk", "") or "").strip() or None
    return (
        int(relevance_score) if relevance_score is not None else None,
        int(importance_score) if importance_score is not None else None,
        json.dumps(list(topics), ensure_ascii=False),
        reason,
    )


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return _as_utc(datetime.fromisoformat(str(value)))
    except ValueError:
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
