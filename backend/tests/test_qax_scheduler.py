from __future__ import annotations

import unittest
from datetime import datetime

from app.main import _cron_matches_now


class QaxSchedulerTestCase(unittest.TestCase):
    """覆盖 QAX 定时扫描 cron 命中逻辑，避免配置存在但线程永远不执行。"""

    def test_cron_matches_hourly_rule(self) -> None:
        self.assertTrue(_cron_matches_now("0 * * * *", datetime(2026, 4, 30, 10, 0)))
        self.assertFalse(_cron_matches_now("0 * * * *", datetime(2026, 4, 30, 10, 5)))

    def test_cron_matches_step_and_weekday_rule(self) -> None:
        self.assertTrue(_cron_matches_now("*/15 9-18 * * 1-5", datetime(2026, 4, 30, 9, 30)))
        self.assertFalse(_cron_matches_now("*/15 9-18 * * 1-5", datetime(2026, 5, 2, 20, 30)))


if __name__ == "__main__":
    unittest.main()
