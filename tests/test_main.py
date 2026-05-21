from __future__ import annotations

import unittest
from datetime import UTC, datetime

from main import should_run_scheduled


class MainTests(unittest.TestCase):
    def test_should_run_scheduled_matches_kyiv_summer_hour(self) -> None:
        self.assertTrue(should_run_scheduled(datetime(2026, 5, 20, 6, 0, tzinfo=UTC)))
        self.assertTrue(should_run_scheduled(datetime(2026, 5, 20, 18, 0, tzinfo=UTC)))
        self.assertFalse(should_run_scheduled(datetime(2026, 5, 20, 8, 0, tzinfo=UTC)))

    def test_should_run_scheduled_matches_kyiv_winter_hour(self) -> None:
        self.assertTrue(should_run_scheduled(datetime(2026, 1, 20, 7, 0, tzinfo=UTC)))
        self.assertTrue(should_run_scheduled(datetime(2026, 1, 20, 19, 0, tzinfo=UTC)))
        self.assertFalse(should_run_scheduled(datetime(2026, 1, 20, 6, 0, tzinfo=UTC)))


if __name__ == "__main__":
    unittest.main()
