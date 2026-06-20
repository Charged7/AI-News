"""Tests for OpenAI-based impact classification."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from impact_ai import (
    ImpactClassificationError,
    ImpactDecision,
    _classify_news_items_with_openai,
    _parse_impact_response,
    build_impact_messages,
    classify_news_importance,
    select_important_news,
)
from rss import NewsItem


class ImpactAiTests(unittest.TestCase):
    def test_classify_news_importance_requires_api_key(self) -> None:
        item = NewsItem("Title", "Text", "https://example.test", None, "Source")

        with self.assertRaises(ImpactClassificationError):
            classify_news_importance([item], api_key="")

    def test_parse_impact_response_returns_decisions(self) -> None:
        item = NewsItem("Title", "Text", "https://example.test", None, "Source")

        result = _parse_impact_response(
            """
            {"items":[{"link":"https://example.test","is_important":true,"impact_score":91,
            "impact_level":"critical","category":"politics","event_type":"war_escalation",
            "scope":"global","reason_uk":"Міжнародна ескалація."}]}
            """,
            [item],
        )

        decision = result["https://example.test"]
        self.assertTrue(decision.is_important)
        self.assertEqual(decision.impact_score, 91)
        self.assertEqual(decision.event_type, "war_escalation")

    def test_parse_impact_response_can_match_by_short_item_id(self) -> None:
        item = NewsItem("Title", "Text", "https://example.test/full?with=query", None, "Source")

        result = _parse_impact_response(
            """
            {"items":[{"id":"item_1","is_important":true,"impact_score":86,
            "impact_level":"high","category":"politics","event_type":"sanctions",
            "scope":"global","reason_uk":"Важлива міжнародна подія."}]}
            """,
            [item],
        )

        self.assertIn("https://example.test/full?with=query", result)
        self.assertEqual(result["https://example.test/full?with=query"].link, item.link)

    def test_parse_impact_response_rejects_missing_items(self) -> None:
        item = NewsItem("Title", "Text", "https://example.test", None, "Source")

        with self.assertRaisesRegex(ImpactClassificationError, "incomplete"):
            _parse_impact_response('{"items":[]}', [item])

    def test_select_important_news_applies_threshold_and_unlimited_max_items(self) -> None:
        first = NewsItem("War", "Major escalation.", "https://first.test", None, "Reuters")
        second = NewsItem("Final", "Title fight.", "https://second.test", None, "AP")
        low = NewsItem("Guide", "How to sleep.", "https://low.test", None, "Blog")

        with patch(
            "impact_ai.classify_news_importance",
            return_value={
                "https://first.test": ImpactDecision("https://first.test", True, 95, "critical", "politics", "war", "global", "Важливо."),
                "https://second.test": ImpactDecision("https://second.test", True, 80, "high", "sports", "title_fight", "global", "Важливо."),
                "https://low.test": ImpactDecision("https://low.test", False, 20, "low", "lifestyle", "guide", "local", "Не подія."),
            },
        ):
            selected = select_important_news([first, second, low], min_score=75, max_items=0)

        self.assertEqual(selected, [first, second])

    def test_classify_news_importance_batches_openai_requests(self) -> None:
        first = NewsItem("First", "Text", "https://first.test", None, "Source")
        second = NewsItem("Second", "Text", "https://second.test", None, "Source")

        with patch(
            "impact_ai._classify_news_items_with_openai",
            side_effect=[
                {
                    "https://first.test": SimpleNamespace(
                        link="https://first.test",
                        is_important=True,
                        impact_score=90,
                    )
                },
                {
                    "https://second.test": SimpleNamespace(
                        link="https://second.test",
                        is_important=False,
                        impact_score=30,
                    )
                },
            ],
        ) as openai_classifier:
            result = classify_news_importance(
                [first, second],
                api_key="test-key",
                model="test-model",
                batch_size=1,
                max_tokens=123,
            )

        self.assertEqual(set(result), {"https://first.test", "https://second.test"})
        self.assertEqual(openai_classifier.call_count, 2)
        self.assertEqual(openai_classifier.call_args_list[0].args[0], [first])
        self.assertEqual(openai_classifier.call_args_list[0].kwargs["max_tokens"], 123)

    def test_classify_news_importance_retries_missing_batch_items(self) -> None:
        first = NewsItem("First", "Text", "https://first.test", None, "Source")
        second = NewsItem("Second", "Text", "https://second.test", None, "Source")

        with patch(
            "impact_ai._classify_news_items_with_openai",
            side_effect=[
                {
                    "https://first.test": ImpactDecision(
                        "https://first.test",
                        True,
                        90,
                        "critical",
                        "politics",
                        "war",
                        "global",
                        "Важливо.",
                    )
                },
                {
                    "https://second.test": ImpactDecision(
                        "https://second.test",
                        False,
                        20,
                        "low",
                        "lifestyle",
                        "guide",
                        "local",
                        "Неважливо.",
                    )
                },
            ],
        ) as openai_classifier:
            result = classify_news_importance(
                [first, second],
                api_key="test-key",
                model="test-model",
                batch_size=2,
                max_tokens=123,
                retry_missing_limit=1,
            )

        self.assertEqual(set(result), {"https://first.test", "https://second.test"})
        self.assertEqual(openai_classifier.call_count, 2)
        self.assertEqual(openai_classifier.call_args_list[1].args[0], [second])

    def test_classify_news_importance_falls_back_when_retry_is_still_missing(self) -> None:
        item = NewsItem("Title", "Text", "https://missing.test", None, "Source", source_category="world")

        with patch("impact_ai._classify_news_items_with_openai", return_value={}):
            result = classify_news_importance(
                [item],
                api_key="test-key",
                model="test-model",
                batch_size=1,
                max_tokens=123,
            )

        decision = result["https://missing.test"]
        self.assertFalse(decision.is_important)
        self.assertEqual(decision.impact_score, 0)
        self.assertEqual(decision.event_type, "unclassified")

    def test_openai_request_uses_json_mode_and_rejects_truncation(self) -> None:
        item = NewsItem("Title", "Text", "https://example.test", None, "Source")
        create = MagicMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="length",
                        message=SimpleNamespace(content='{"items":['),
                    )
                ]
            )
        )
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        openai_module = SimpleNamespace(OpenAI=MagicMock(return_value=client))

        with patch.dict("sys.modules", {"openai": openai_module}):
            with self.assertRaisesRegex(ImpactClassificationError, "truncated"):
                _classify_news_items_with_openai(
                    [item],
                    api_key="test-key",
                    model="test-model",
                    max_tokens=123,
                )

        request = create.call_args.kwargs
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertEqual(request["temperature"], 0)

    def test_build_impact_messages_includes_source_metadata(self) -> None:
        item = NewsItem(
            "Title",
            "Text",
            "https://example.test",
            None,
            "Source",
            source_category="world",
            source_priority="high",
        )

        messages = build_impact_messages([item])

        self.assertIn("Source category: world", messages[1]["content"])
        self.assertIn("Source priority: high", messages[1]["content"])
        self.assertIn("ID: item_1", messages[1]["content"])
        self.assertIn("рівно один JSON object", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
