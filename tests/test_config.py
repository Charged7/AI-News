"""Tests for environment configuration helpers."""

import os
import unittest
from unittest.mock import patch

from config import _env_int


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


if __name__ == "__main__":
    unittest.main()
