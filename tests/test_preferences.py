"""Tests for loading and fingerprinting the preference profile."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from preferences import PreferencesError, load_news_preferences, preferences_fingerprint


class PreferencesTests(unittest.TestCase):
    def test_inline_preferences_override_file(self) -> None:
        self.assertEqual(
            load_news_preferences("missing.md", inline_preferences="  football  "),
            "football",
        )

    def test_loads_utf8_profile_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "preferences.md"
            path.write_text("# Політика\nВажливі рішення", encoding="utf-8")

            self.assertIn("Важливі рішення", load_news_preferences(path, ""))

    def test_rejects_missing_or_empty_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.md"
            with self.assertRaises(PreferencesError):
                load_news_preferences(missing, "")

    def test_fingerprint_changes_with_meaningful_profile_edit(self) -> None:
        self.assertNotEqual(
            preferences_fingerprint("football"),
            preferences_fingerprint("football and boxing"),
        )


if __name__ == "__main__":
    unittest.main()
