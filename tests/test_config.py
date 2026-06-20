"""Tests for project configuration helpers."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import RSSSource, _env_int, _load_rss_sources


class ConfigTests(unittest.TestCase):
    def test_env_int_uses_default_for_missing_or_empty_value(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_env_int("TEST_INT", 8), 8)

        with patch.dict(os.environ, {"TEST_INT": ""}):
            self.assertEqual(_env_int("TEST_INT", 8), 8)

    def test_env_int_rejects_non_integer_value(self) -> None:
        with patch.dict(os.environ, {"TEST_INT": "abc"}):
            with self.assertRaisesRegex(ValueError, "TEST_INT must be an integer"):
                _env_int("TEST_INT", 8)

    def test_load_rss_sources_reads_enabled_items_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sources.json"
            path.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "name": "World Feed",
                                "url": "https://example.test/world.xml",
                                "category": "world",
                                "priority": "high",
                                "enabled": True,
                            },
                            {
                                "name": "Disabled",
                                "url": "https://example.test/disabled.xml",
                                "enabled": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            sources = _load_rss_sources(path)

        self.assertEqual(
            sources,
            [
                RSSSource(
                    name="World Feed",
                    url="https://example.test/world.xml",
                    category="world",
                    priority="high",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
