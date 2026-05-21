from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

from rss import NewsItem


@dataclass(frozen=True)
class SentNewsRecord:
    link: str
    title: str
    source: str
    sent_at: datetime


class SentNewsStore:
    def __init__(self, path: str | Path, retention_days: int) -> None:
        self.path = Path(path)
        self.retention_days = retention_days
        self.records: dict[str, SentNewsRecord] = {}

    @classmethod
    def load(cls, path: str | Path, retention_days: int) -> "SentNewsStore":
        store = cls(path, retention_days)
        if not store.path.exists():
            return store

        data = json.loads(store.path.read_text(encoding="utf-8"))
        for raw_record in data.get("items", []):
            link = str(raw_record.get("link", "")).strip()
            sent_at = _parse_datetime(raw_record.get("sent_at"))
            if not link or sent_at is None:
                continue
            store.records[_link_key(link)] = SentNewsRecord(
                link=link,
                title=str(raw_record.get("title", "")).strip(),
                source=str(raw_record.get("source", "")).strip(),
                sent_at=sent_at,
            )
        return store

    def filter_unsent(self, items: Iterable[NewsItem]) -> list[NewsItem]:
        return [item for item in items if _link_key(item.link) not in self.records]

    def mark_sent(self, items: Iterable[NewsItem], now: datetime | None = None) -> None:
        sent_at = _as_utc(now or datetime.now(UTC))
        for item in items:
            self.records[_link_key(item.link)] = SentNewsRecord(
                link=item.link,
                title=item.title,
                source=item.source,
                sent_at=sent_at,
            )

    def prune(self, now: datetime | None = None) -> None:
        cutoff = _as_utc(now or datetime.now(UTC)) - timedelta(days=self.retention_days)
        self.records = {
            link_key: record
            for link_key, record in self.records.items()
            if record.sent_at >= cutoff
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        records = sorted(self.records.values(), key=lambda record: record.sent_at, reverse=True)
        data = {
            "items": [
                {
                    "link": record.link,
                    "title": record.title,
                    "source": record.source,
                    "sent_at": record.sent_at.isoformat(),
                }
                for record in records
            ]
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _link_key(link: str) -> str:
    return link.strip().lower()


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
