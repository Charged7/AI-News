from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from rss import NewsItem, deduplicate_news, extract_image, is_recent


class RssTests(unittest.TestCase):
    def test_is_recent_keeps_only_items_inside_lookback_window(self) -> None:
        now = datetime(2026, 5, 20, 9, 0, tzinfo=UTC)
        recent = NewsItem("A", "Desc", "https://a.test", None, "Source", now - timedelta(hours=1))
        old = NewsItem("B", "Desc", "https://b.test", None, "Source", now - timedelta(hours=25))
        undated = NewsItem("C", "Desc", "https://c.test", None, "Source", None)

        self.assertTrue(is_recent(recent, 24, now))
        self.assertFalse(is_recent(old, 24, now))
        self.assertFalse(is_recent(undated, 24, now))

    def test_extract_image_prefers_media_content(self) -> None:
        entry = {
            "media_content": [{"url": "https://cdn.test/image.jpg", "type": "image/jpeg"}],
            "summary": '<p><img src="https://cdn.test/other.jpg"></p>',
        }

        self.assertEqual(extract_image(entry), "https://cdn.test/image.jpg")

    def test_extract_image_uses_enclosure_or_html(self) -> None:
        enclosure_entry = {"enclosures": [{"href": "https://cdn.test/photo.png", "type": "image/png"}]}
        html_entry = {"summary": '<p>Hello <img src="https://cdn.test/html.webp"></p>'}

        self.assertEqual(extract_image(enclosure_entry), "https://cdn.test/photo.png")
        self.assertEqual(extract_image(html_entry), "https://cdn.test/html.webp")

    def test_deduplicate_news_by_link_then_title(self) -> None:
        first = NewsItem("Same Title", "Desc", "https://a.test", None, "A")
        duplicate_link = NewsItem("Different", "Desc", "https://a.test", None, "B")
        duplicate_title = NewsItem("same title", "Desc", "https://b.test", None, "B")
        unique = NewsItem("Unique", "Desc", "https://c.test", None, "C")

        self.assertEqual(deduplicate_news([first, duplicate_link, duplicate_title, unique]), [first, unique])


if __name__ == "__main__":
    unittest.main()
