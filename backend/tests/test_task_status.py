from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

from app.api import effective_task_delay_days, is_task_due_soon


class TaskStatusRuleTestCase(unittest.TestCase):
    def test_effective_delay_counts_open_overdue_task_without_delay_days(self) -> None:
        task = SimpleNamespace(
            main_status="in_progress",
            delay_days=0,
            end_at=datetime(2026, 5, 7, 18, 0, 0),
        )
        now = datetime(2026, 5, 9, 9, 0, 0)
        self.assertEqual(effective_task_delay_days(task, now), 2)
        self.assertFalse(is_task_due_soon(task, now))

    def test_effective_delay_ignores_closed_overdue_task(self) -> None:
        task = SimpleNamespace(
            main_status="done",
            delay_days=0,
            end_at=datetime(2026, 5, 7, 18, 0, 0),
        )
        now = datetime(2026, 5, 9, 9, 0, 0)
        self.assertEqual(effective_task_delay_days(task, now), 0)

    def test_due_soon_excludes_already_delayed_task(self) -> None:
        task = SimpleNamespace(
            main_status="not_started",
            delay_days=3,
            end_at=datetime(2026, 5, 10, 18, 0, 0),
        )
        now = datetime(2026, 5, 9, 9, 0, 0)
        self.assertEqual(effective_task_delay_days(task, now), 3)
        self.assertFalse(is_task_due_soon(task, now))


if __name__ == "__main__":
    unittest.main()
