from __future__ import annotations

import unittest
from datetime import datetime

from app.api import infer_task_status_by_time


class TaskStatusInferenceTestCase(unittest.TestCase):
    def test_before_start_is_not_started(self) -> None:
        start_at = datetime(2026, 5, 1, 0, 0, 0)
        end_at = datetime(2026, 5, 2, 0, 0, 0)
        now = datetime(2026, 4, 30, 23, 59, 0)
        self.assertEqual(infer_task_status_by_time(start_at, end_at, now), "not_started")

    def test_between_is_in_progress(self) -> None:
        start_at = datetime(2026, 5, 1, 0, 0, 0)
        end_at = datetime(2026, 5, 2, 0, 0, 0)
        now = datetime(2026, 5, 1, 10, 0, 0)
        self.assertEqual(infer_task_status_by_time(start_at, end_at, now), "in_progress")

    def test_reach_end_is_done(self) -> None:
        start_at = datetime(2026, 5, 1, 0, 0, 0)
        end_at = datetime(2026, 5, 2, 0, 0, 0)
        now = datetime(2026, 5, 2, 0, 0, 0)
        self.assertEqual(infer_task_status_by_time(start_at, end_at, now), "done")


if __name__ == "__main__":
    unittest.main()
