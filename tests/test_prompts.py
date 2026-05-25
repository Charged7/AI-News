"""Тести для побудови OpenAI prompt-меседжів під batch-обробку новин."""

from __future__ import annotations

import unittest

from prompts import OPENAI_NEWS_SYSTEM_PROMPT, OPENAI_NEWS_USER_PROMPT_TEMPLATE, build_openai_messages
from rss import NewsItem


class PromptTests(unittest.TestCase):
    """Перевіряє, що prompt містить усі потрібні новини та інструкції."""

    def test_build_openai_messages_includes_item_list(self) -> None:
        items = [
            NewsItem("Title 1", "Desc 1", "https://example.test/1", None, "The Verge"),
            NewsItem("Title 2", "Desc 2", "https://example.test/2", None, "TechCrunch"),
        ]

        messages = build_openai_messages(items)

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Не вигадуй фактів", OPENAI_NEWS_SYSTEM_PROMPT)
        self.assertIn("Не додавай жодних emoji", OPENAI_NEWS_SYSTEM_PROMPT)
        self.assertIn("Поверни JSON у форматі", OPENAI_NEWS_USER_PROMPT_TEMPLATE)
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("Source: The Verge", messages[1]["content"])
        self.assertIn("Link: https://example.test/1", messages[1]["content"])
        self.assertIn("Source: TechCrunch", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
