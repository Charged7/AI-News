"""Tests for story-level duplicate detection."""

from __future__ import annotations

import unittest

from ai import AiNewsText
from news_dedup import (
    are_similar_stories,
    build_story_fingerprint,
    filter_duplicate_story_items,
    link_key,
)
from rss import NewsItem


class NewsDedupTests(unittest.TestCase):
    def test_filters_same_story_from_different_sources(self) -> None:
        first = NewsItem(
            "Vance arrives in Switzerland for US-Iran talks",
            "Both nations seek a durable end to their war.",
            "https://www.aljazeera.com/news/2026/6/21/vance-arrives-in-switzerland-for-us-iran-talks",
            None,
            "Al Jazeera",
        )
        duplicate = NewsItem(
            "Vance arrives in Switzerland for Iran peace talks with Hormuz in spotlight",
            "The US vice president hopes to make progress on Lebanon and Iran.",
            "https://www.politico.eu/article/jd-vance-switzerland-iran-peace-talks-strait-of-hormuz/",
            None,
            "Politico Europe",
        )

        summaries = {
            link_key(first.link): AiNewsText(
                "Венс прибув до Швейцарії для переговорів між США та Іраном",
                "Обидві країни прагнуть домовленості, поки триває напруга навколо Ірану.",
            ),
            link_key(duplicate.link): AiNewsText(
                "Венс прибув до Швейцарії для переговорів щодо миру з Іраном",
                "Віцепрезидент США веде переговори про Іран і Ормузьку протоку.",
            ),
        }

        result = filter_duplicate_story_items([first, duplicate], summaries)

        self.assertEqual(result.unique_items, [first])
        self.assertEqual(result.duplicate_items, [duplicate])

    def test_keeps_different_iran_stories_when_overlap_is_too_small(self) -> None:
        talks = NewsItem(
            "Vance arrives in Switzerland for US-Iran talks",
            "Peace talks begin in Switzerland.",
            "https://example.test/vance-switzerland-iran-talks",
            None,
            "Source",
        )
        attack = NewsItem(
            "Oil prices jump after strikes near Gulf shipping route",
            "Markets reacted after a separate military escalation.",
            "https://example.test/oil-prices-gulf-shipping-route",
            None,
            "Source",
        )

        summaries = {
            link_key(talks.link): AiNewsText(
                "Венс прибув до Швейцарії для переговорів з Іраном",
                "США та Іран обговорюють мирну угоду.",
            ),
            link_key(attack.link): AiNewsText(
                "Ціни на нафту зросли після ударів біля морського маршруту",
                "Ринки відреагували на окрему військову ескалацію.",
            ),
        }

        result = filter_duplicate_story_items([talks, attack], summaries)

        self.assertEqual(result.unique_items, [talks, attack])
        self.assertEqual(result.duplicate_items, [])

    def test_matches_against_existing_fingerprint(self) -> None:
        sent = NewsItem(
            "Vance arrives in Switzerland for US-Iran talks",
            "Both nations seek a durable end to their war.",
            "https://example.test/vance-arrives-in-switzerland-for-us-iran-talks",
            None,
            "Source",
        )
        candidate = NewsItem(
            "JD Vance in Switzerland for Iran peace talks",
            "The US vice president joined negotiations.",
            "https://example.test/jd-vance-switzerland-iran-peace-talks",
            None,
            "Source",
        )
        sent_fingerprint = build_story_fingerprint(sent)

        result = filter_duplicate_story_items(
            [candidate],
            {
                link_key(candidate.link): AiNewsText(
                    "Венс у Швейцарії для переговорів з Іраном",
                    "Віцепрезидент США бере участь у переговорах.",
                )
            },
            existing_fingerprints=[sent_fingerprint],
        )

        self.assertEqual(result.unique_items, [])
        self.assertEqual(result.duplicate_items, [candidate])

    def test_similarity_requires_enough_shared_tokens(self) -> None:
        self.assertFalse(are_similar_stories("iran talks peace", "iran oil market"))


if __name__ == "__main__":
    unittest.main()
