"""RSS-завантаження, очищення, дедуплікація та відбір нових новин."""

import html
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any, Iterable

from config import RSSSource

try:
    import feedparser
except ImportError:  # pragma: no cover - handled when fetching feeds
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - regex fallback keeps helpers usable
    BeautifulSoup = None

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewsItem:
    """Уніфікований запис новини, який далі використовують AI та Telegram."""

    title: str
    description: str
    link: str
    image: str | None
    source: str
    published_at: datetime | None = None


def fetch_recent_news(
        sources: Iterable[RSSSource],
        lookback_hours: int,
        now: datetime | None = None,
) -> list[NewsItem]:
    """Збирає новини з усіх RSS-джерел за вказаний часовий проміжок."""
    if feedparser is None:
        raise RuntimeError("feedparser is not installed. Run: pip install -r requirements.txt")

    now_utc = _as_utc(now or datetime.now(UTC))
    items: list[NewsItem] = []

    for source in sources:
        logger.info("Fetching RSS source: %s", source.name)
        feed = feedparser.parse(source.url)
        entries = getattr(feed, "entries", [])
        if getattr(feed, "bozo", False):
            logger.warning("RSS parser warning for %s: %s", source.name, getattr(feed, "bozo_exception", "unknown"))
            if not entries:
                raise RuntimeError(f"Could not fetch or parse RSS source: {source.name}")

        for entry in entries:
            item = normalize_entry(entry, source.name)
            if item and is_recent(item, lookback_hours, now_utc):
                items.append(item)

    return sort_news(deduplicate_news(items))


def normalize_entry(entry: Any, source_name: str) -> NewsItem | None:
    """Перетворює сирий RSS entry на NewsItem або пропускає його, якщо даних замало."""
    title = clean_text(_entry_get(entry, "title", ""))
    link = str(_entry_get(entry, "link", "") or "").strip()
    description_html = _entry_description(entry)
    description = clean_text(description_html)
    published_at = parse_entry_datetime(entry)

    if not title or not link:
        return None

    return NewsItem(
        title=title,
        description=description,
        link=link,
        image=extract_image(entry),
        source=source_name,
        published_at=published_at,
    )


def parse_entry_datetime(entry: Any) -> datetime | None:
    """Витягує дату публікації з різних можливих RSS-полів."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = _entry_get(entry, key)
        if isinstance(value, struct_time):
            return datetime(*value[:6], tzinfo=UTC)

    for key in ("published", "updated", "created"):
        value = _entry_get(entry, key)
        if value:
            try:
                parsed = parsedate_to_datetime(str(value))
            except (TypeError, ValueError):
                continue
            return _as_utc(parsed)

    return None


def is_recent(item: NewsItem, lookback_hours: int, now: datetime | None = None) -> bool:
    """Перевіряє, чи потрапляє новина у потрібне вікно lookback."""
    if item.published_at is None:
        return False
    now_utc = _as_utc(now or datetime.now(UTC))
    published_utc = _as_utc(item.published_at)
    return now_utc - timedelta(hours=lookback_hours) <= published_utc <= now_utc


def deduplicate_news(items: Iterable[NewsItem]) -> list[NewsItem]:
    """Прибирає дублікати спершу за link, потім за нормалізованим title."""
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[NewsItem] = []

    for item in items:
        link_key = item.link.strip().lower()
        title_key = normalize_title(item.title)

        if link_key and link_key in seen_links:
            continue
        if title_key and title_key in seen_titles:
            continue

        if link_key:
            seen_links.add(link_key)
        if title_key:
            seen_titles.add(title_key)
        unique.append(item)

    return unique


def sort_news(items: Iterable[NewsItem]) -> list[NewsItem]:
    """Сортує новини від найновішої до найстарішої."""
    return sorted(
        items,
        key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


def extract_image(entry: Any) -> str | None:
    """Шукає картинку в media, enclosure, links або HTML всередині RSS entry."""
    for key in ("media_content", "media_thumbnail"):
        image = _first_media_url(_entry_get(entry, key))
        if image:
            return image

    image = _first_media_url(_entry_get(entry, "enclosures"))
    if image:
        return image

    links = _entry_get(entry, "links") or []
    for link in links:
        rel = str(_dict_get(link, "rel", "") or "").lower()
        content_type = str(_dict_get(link, "type", "") or "").lower()
        href = _dict_get(link, "href")
        if href and (rel == "enclosure" or content_type.startswith("image/") or _looks_like_image_url(str(href))):
            return str(href)

    for html_value in _entry_html_values(entry):
        image = _extract_first_img_src(html_value)
        if image:
            return image

    return None


def clean_text(value: str) -> str:
    """Очищає HTML, схлопує пробіли й робить текст придатним для повідомлення."""
    value = html.unescape(str(value or ""))
    if BeautifulSoup is not None:
        text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    else:
        text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([.,!?;:])", r"\1", text)


def normalize_title(title: str) -> str:
    """Готує title до порівняння для дедуплікації."""
    normalized = clean_text(title).lower()
    normalized = re.sub(r"[^a-z0-9а-яіїєґ]+", " ", normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


def _entry_get(entry: Any, key: str, default: Any = None) -> Any:
    """Універсально читає поле з dict-подібного або object-подібного entry."""
    if hasattr(entry, "get"):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _dict_get(value: Any, key: str, default: Any = None) -> Any:
    """Читає поле з вкладеного елемента RSS, незалежно від його типу."""
    if hasattr(value, "get"):
        return value.get(key, default)
    return getattr(value, key, default)


def _entry_description(entry: Any) -> str:
    """Дістає опис новини з summary, description або content."""
    for key in ("summary", "description"):
        value = _entry_get(entry, key)
        if value:
            return str(value)

    content = _entry_get(entry, "content") or []
    if content:
        first = content[0]
        return str(_dict_get(first, "value", "") or "")

    return ""


def _entry_html_values(entry: Any) -> list[str]:
    """Збирає HTML-поля entry для пошуку зображень у body."""
    values = [_entry_description(entry)]
    content = _entry_get(entry, "content") or []
    values.extend(str(_dict_get(item, "value", "") or "") for item in content)
    return [value for value in values if value]


def _first_media_url(items: Any) -> str | None:
    """Повертає перший придатний URL із media/enclosure списку."""
    if not items:
        return None
    if isinstance(items, dict):
        items = [items]

    for item in items:
        url = _dict_get(item, "url") or _dict_get(item, "href")
        content_type = str(_dict_get(item, "type", "") or "").lower()
        medium = str(_dict_get(item, "medium", "") or "").lower()
        if url and (medium == "image" or content_type.startswith("image/") or _looks_like_image_url(str(url))):
            return str(url)
    return None


def _extract_first_img_src(value: str) -> str | None:
    """Дістає src першого <img> із HTML-рядка."""
    if BeautifulSoup is not None:
        soup = BeautifulSoup(value, "html.parser")
        image = soup.find("img")
        if image and image.get("src"):
            return str(image["src"])

    match = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", value, flags=re.IGNORECASE)
    if match:
        return html.unescape(match.group(1))
    return None


def _looks_like_image_url(value: str) -> bool:
    """Перевіряє, чи схожа URL на пряме посилання на картинку."""
    return bool(re.search(r"\.(jpe?g|png|webp|gif)(\?|$)", value, flags=re.IGNORECASE))


def _as_utc(value: datetime) -> datetime:
    """Нормалізує datetime до UTC, щоб порівняння були стабільними."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
