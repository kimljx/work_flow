from __future__ import annotations

import unittest

from app.services.delay_parser import parse_delay_approval_email


class DelayParserTestCase(unittest.TestCase):
    def test_parse_iso_date(self) -> None:
        result = parse_delay_approval_email("同意: 2026-01-15")
        self.assertTrue(result.ok)
        self.assertEqual(result.action, "APPROVE")
        self.assertEqual(result.date.year, 2026)

    def test_parse_cn_date_and_ignore_signature(self) -> None:
        result = parse_delay_approval_email("同意：2026年1月15日 请处理\n--\n签名档")
        self.assertTrue(result.ok)
        self.assertEqual(result.action, "APPROVE")
        self.assertEqual(result.date.month, 1)

    def test_parse_reject(self) -> None:
        result = parse_delay_approval_email("拒绝: 当前资源不足")
        self.assertTrue(result.ok)
        self.assertEqual(result.action, "REJECT")


if __name__ == "__main__":
    unittest.main()
