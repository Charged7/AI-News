from __future__ import annotations

import unittest
from unittest.mock import patch

from ai import AISummaryError, _parse_digest_response, summarize_news_digest
from rss import NewsItem


class AiTests(unittest.TestCase):
    def test_summarize_news_digest_requires_api_key(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            summarize_news_digest([item], api_key="")

    def test_summarize_news_digest_requires_items(self) -> None:
        with self.assertRaises(AISummaryError):
            summarize_news_digest([], api_key="test-key")

    def test_summarize_news_digest_raises_when_openai_fails(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            with patch("ai._summarize_digest_with_openai_with_rate_limit_retry", side_effect=RuntimeError("boom")):
                summarize_news_digest([item], api_key="test-key")

    def test_parse_digest_response_requires_digest(self) -> None:
        with self.assertRaises(AISummaryError):
            _parse_digest_response('{"title_uk": "Заголовок"}')

    def test_parse_digest_response_returns_digest(self) -> None:
        result = _parse_digest_response('{"digest_uk": "Короткий дайджест новин."}')

        self.assertEqual(result.digest, "Короткий дайджест новин.")


if __name__ == "__main__":
    unittest.main()
