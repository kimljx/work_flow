from __future__ import annotations

import unittest

from app.models import Template
from app.services.templates import sort_templates, template_matches


class TemplateMatcherTestCase(unittest.TestCase):
    def test_template_sort_is_deterministic(self) -> None:
        templates = [
            Template(id=3, name="c", template_kind="MAIL_REPLY", notify_type="done", priority=100, version=1, enabled=True),
            Template(id=1, name="a", template_kind="MAIL_REPLY", notify_type="done", priority=100, version=2, enabled=True),
            Template(id=2, name="b", template_kind="MAIL_REPLY", notify_type="done", priority=200, version=1, enabled=True),
        ]
        self.assertEqual(sort_templates(templates)[0].id, 2)

    def test_subject_or_body_match(self) -> None:
        template = Template(
            id=1,
            name="done",
            template_kind="MAIL_REPLY",
            notify_type="done",
            priority=100,
            version=1,
            enabled=True,
            subject_rule="完成",
            body_rule="完成",
            content="",
        )
        self.assertTrue(template_matches(template, "任务完成", ""))
        self.assertTrue(template_matches(template, "", "已完成"))


if __name__ == "__main__":
    unittest.main()
