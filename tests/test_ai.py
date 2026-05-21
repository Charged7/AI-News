from __future__ import annotations

import unittest
from unittest.mock import patch

from ai import AISummaryError, _parse_ai_response, summarize_news_item, summarize_news_items
from rss import NewsItem


class AiTests(unittest.TestCase):
    def test_summarize_news_item_requires_api_key(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            summarize_news_item(item, api_key="")

    def test_summarize_news_items_requires_api_key(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            summarize_news_items([item], api_key="")

    def test_summarize_news_items_raises_when_openai_fails(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            with patch("ai._summarize_with_openai_with_rate_limit_retry", side_effect=RuntimeError("boom")):
                summarize_news_items([item], api_key="test-key")

    def test_parse_ai_response_requires_title_and_summary(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            _parse_ai_response('{"title_uk": "Заголовок"}', item)

    def test_parse_ai_response_returns_translated_title_and_summary(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        result = _parse_ai_response('{"title_uk": "Український заголовок", "summary_uk": "Короткий опис."}', item)

        self.assertEqual(result.title, "Український заголовок")
        self.assertEqual(result.summary, "Короткий опис.")


if __name__ == "__main__":
    unittest.main()
