"""Тести для batch-логіки OpenAI та парсингу новинних summary."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ai import (
    AISummaryError,
    AiNewsText,
    _parse_ai_response,
    _summarize_news_items_with_openai,
    summarize_news_items,
)
from rss import NewsItem


class AiTests(unittest.TestCase):
    """Перевіряє, що AI повертає валідні summaries для новин і коректно падає на помилках."""

    def test_summarize_news_items_requires_api_key(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            summarize_news_items([item], api_key="")

    def test_summarize_news_items_requires_items(self) -> None:
        with self.assertRaises(AISummaryError):
            summarize_news_items([], api_key="test-key")

    def test_summarize_news_items_raises_when_openai_fails(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            with patch("ai._summarize_news_items_with_openai", side_effect=RuntimeError("boom")):
                summarize_news_items([item], api_key="test-key")

    def test_summarize_news_items_batches_openai_requests(self) -> None:
        first = NewsItem("First", "First text", "https://first.test", None, "Source")
        second = NewsItem("Second", "Second text", "https://second.test", None, "Source")

        with patch(
            "ai._summarize_news_items_with_openai",
            side_effect=[
                {"https://first.test": AiNewsText("Перший", "Коротко про першу новину.")},
                {"https://second.test": AiNewsText("Другий", "Коротко про другу новину.")},
            ],
        ) as openai_summary:
            result = summarize_news_items(
                [first, second],
                api_key="test-key",
                model="test-model",
                batch_size=1,
                max_tokens=123,
            )

        self.assertEqual(set(result), {"https://first.test", "https://second.test"})
        self.assertEqual(openai_summary.call_count, 2)
        self.assertEqual(openai_summary.call_args_list[0].args[0], [first])
        self.assertEqual(openai_summary.call_args_list[1].args[0], [second])
        self.assertEqual(openai_summary.call_args_list[0].kwargs["max_tokens"], 123)

    def test_openai_request_uses_json_mode_and_rejects_truncation(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")
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
            with self.assertRaisesRegex(AISummaryError, "truncated"):
                _summarize_news_items_with_openai(
                    [item],
                    api_key="test-key",
                    model="test-model",
                    max_tokens=123,
                )

        request = create.call_args.kwargs
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertEqual(request["max_tokens"], 123)

    def test_parse_ai_response_requires_title_and_summary(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        with self.assertRaises(AISummaryError):
            _parse_ai_response(
                '{"items":[{"link":"https://example.test","title_uk":"Заголовок"}]}',
                [item],
            )

    def test_parse_ai_response_returns_translated_title_and_summary(self) -> None:
        item = NewsItem("Title", "<p>Description text.</p>", "https://example.test", None, "Source")

        result = _parse_ai_response(
            '{"items":[{"link":"https://example.test","title_uk":"Український заголовок","summary_uk":"Короткий опис."}]}',
            [item],
        )

        self.assertEqual(result["https://example.test"].title, "Український заголовок")
        self.assertEqual(result["https://example.test"].summary, "Короткий опис.")


if __name__ == "__main__":
    unittest.main()
