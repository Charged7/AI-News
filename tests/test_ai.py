from __future__ import annotations

import unittest

from ai import AISummaryError, fallback_summary, summarize_news_item, summarize_news_items
from rss import NewsItem


class AiTests(unittest.TestCase):
    def test_fallback_summary_strips_html_and_limits_text(self) -> None:
        summary = fallback_summary("<p>Hello <strong>world</strong>.</p><p>Second sentence.</p>", max_chars=40)

        self.assertEqual(summary, "Hello world. Second sentence.")

    def test_summarize_news_item_uses_fallback_without_api_key(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        self.assertEqual(summarize_news_item(item, api_key=""), "Description text.")

    def test_summarize_news_items_can_disable_ai_even_with_key(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        self.assertEqual(
            summarize_news_items([item], api_key="not-used", use_ai=False),
            {"https://example.test": "Description text."},
        )

    def test_summarize_news_items_can_require_ai(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            summarize_news_items([item], api_key="", use_ai=True, require_ai=True)


if __name__ == "__main__":
    unittest.main()
