"""Tests for bounded news-cycle helpers."""

from __future__ import annotations

import unittest

from news_pipeline import limit_candidates
from rss import NewsItem


class NewsPipelineTests(unittest.TestCase):
    def test_limit_candidates_keeps_newest_first_prefix(self) -> None:
        items = [
            NewsItem("First", "Text", "https://first.test", None, "Source"),
            NewsItem("Second", "Text", "https://second.test", None, "Source"),
            NewsItem("Third", "Text", "https://third.test", None, "Source"),
        ]

        self.assertEqual(limit_candidates(items, max_candidates=2), items[:2])

    def test_limit_candidates_zero_means_unlimited(self) -> None:
        items = [NewsItem("First", "Text", "https://first.test", None, "Source")]

        self.assertEqual(limit_candidates(items, max_candidates=0), items)


if __name__ == "__main__":
    unittest.main()
