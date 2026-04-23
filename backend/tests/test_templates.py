from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.models import Template
from app.services.templates import (
    extract_template_placeholders,
    sort_templates,
    template_allowed_variables,
    template_matches,
    validate_template_content,
)


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

    def test_template_variable_catalog_matches_notify_type(self) -> None:
        variables = template_allowed_variables("MAIL_SEND", "task_created")
        self.assertIn("creator_name", variables)
        self.assertIn("subtask_summary", variables)
        self.assertNotIn("delay_request_id", variables)

        delay_variables = template_allowed_variables("MAIL_SEND", "delay_approval")
        self.assertIn("delay_request_id", delay_variables)
        self.assertIn("apply_reason", delay_variables)

        reply_variables = template_allowed_variables("MAIL_REPLY", "task_done")
        self.assertEqual(reply_variables, set())

    def test_extract_template_placeholders(self) -> None:
        placeholders = extract_template_placeholders("负责人：{owner_name}\n任务创建人：{creator_name}\n负责人：{owner_name}")
        self.assertEqual(placeholders, ["creator_name", "owner_name"])

    def test_validate_template_content_rejects_invalid_variables(self) -> None:
        with self.assertRaises(HTTPException) as context:
            validate_template_content("MAIL_SEND", "task_created", "任务名称：{task_title}\n错误变量：{creator}")
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("creator", context.exception.detail)

    def test_validate_template_content_accepts_valid_variables(self) -> None:
        validate_template_content(
            "MAIL_SEND",
            "delay_approval",
            "负责人：{owner_name}\n任务创建人：{creator_name}\n延期申请编号：{delay_request_id}\n原因：{apply_reason}",
        )


if __name__ == "__main__":
    unittest.main()
