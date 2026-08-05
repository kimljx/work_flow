from __future__ import annotations

import unittest

from fastapi import HTTPException

from app.models import Template
from app.services.templates import (
    extract_template_placeholders,
    sort_templates,
    select_reply_template,
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

    def test_reply_template_uses_first_status_including_after_newline(self) -> None:
        done = Template(id=1, name="已完成", template_kind="MAIL_REPLY", notify_type="task_done", priority=120, version=1, enabled=True, body_rule="已完成|完成")
        in_progress = Template(id=2, name="进行中", template_kind="MAIL_REPLY", notify_type="task_in_progress", priority=110, version=1, enabled=True, body_rule="进行中")

        self.assertEqual(select_reply_template([done, in_progress], "", "进行中，已完成第一点").id, in_progress.id)
        self.assertEqual(select_reply_template([done, in_progress], "", "进行中\n已完成第一点").id, in_progress.id)
        self.assertEqual(select_reply_template([done, in_progress], "", "已完成\n后续说明：仍在进行中").id, done.id)

    def test_reply_template_keeps_first_status_across_common_sentence_separators(self) -> None:
        done = Template(id=1, name="已完成", template_kind="MAIL_REPLY", notify_type="task_done", priority=120, version=1, enabled=True, body_rule="已完成|完成")
        in_progress = Template(id=2, name="进行中", template_kind="MAIL_REPLY", notify_type="task_in_progress", priority=110, version=1, enabled=True, body_rule="进行中")

        for separator in ("。", ".", "；", ";", "、", "：", ":", "！", "!", "？", "?"):
            with self.subTest(separator=separator):
                selected = select_reply_template([done, in_progress], "", f"进行中{separator}已完成第一点")
                self.assertEqual(selected.id, in_progress.id)

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

    def test_validate_template_content_accepts_default_task_context_variables(self) -> None:
        validate_template_content(
            "MAIL_SEND",
            "task_created",
            "当前提醒重点：{remind_focus}\n主任务备注：{task_remark}",
        )


if __name__ == "__main__":
    unittest.main()
