from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_notification_chain.db"

from app.bootstrap import DEFAULT_TEMPLATES
from app.db import Base, SessionLocal, engine
from app.models import NotificationRecipient, Task, TaskMember, TaskSubtask, Template, User
from app.services.notifications import create_notification_with_recipients, preview_notification_content


class NotificationChainTestCase(unittest.TestCase):
    """覆盖任务创建后通知渲染与预览的关键链路。"""

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            admin = User(
                username="admin",
                password_hash="x",
                role="admin",
                name="系统管理员",
                email="admin@example.com",
                ip_address="10.0.0.1",
                is_active=True,
            )
            owner = User(
                username="owner",
                password_hash="x",
                role="member",
                name="任务负责人",
                email="owner@example.com",
                ip_address="10.0.0.3",
                is_active=True,
            )
            member = User(
                username="member",
                password_hash="x",
                role="member",
                name="默认成员",
                email="member@example.com",
                ip_address="10.0.0.2",
                is_active=True,
            )
            db.add_all([admin, owner, member])
            db.flush()

            task = Task(
                title="链路测试任务",
                content="主任务正文说明",
                priority="medium",
                remark="主任务备注说明",
                start_at=datetime(2026, 4, 1, 9, 0, 0),
                end_at=datetime(2026, 4, 2, 18, 0, 0),
                planned_minutes=33 * 60,
                due_remind_days=1,
                created_by=admin.id,
            )
            db.add(task)
            db.flush()

            db.add(TaskMember(task_id=task.id, user_id=owner.id, member_role="owner"))
            db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="participant"))
            db.add(
                TaskSubtask(
                    task_id=task.id,
                    title="整理测试子任务",
                    content="整理并校验链路数据。",
                    assignee_id=member.id,
                    sort_order=0,
                )
            )
            for item in DEFAULT_TEMPLATES:
                db.add(Template(**item))
            db.commit()

    def test_outbound_notify_types_have_default_templates(self) -> None:
        """对外发送类通知都应有默认模板，避免创建任务后找不到正文。"""
        outbound = {"task_created", "manual_remind", "due_remind", "delay_approval"}
        with SessionLocal() as db:
            for notify_type in outbound:
                for template_kind in ("MAIL_SEND", "QAX_SEND"):
                    template = (
                        db.query(Template)
                        .filter(
                            Template.template_kind == template_kind,
                            Template.notify_type == notify_type,
                            Template.enabled.is_(True),
                            Template.is_default.is_(True),
                        )
                        .first()
                    )
                    self.assertIsNotNone(template, f"{template_kind}/{notify_type} 缺少默认模板")

    def test_notification_creation_uses_recipient_subtasks(self) -> None:
        """真实创建通知时，应按接收人过滤子任务，并正确渲染负责人与创建人。"""
        with SessionLocal() as db:
            notification = create_notification_with_recipients(
                db=db,
                task_id=1,
                channel="qax",
                notify_type="task_created",
                content_snapshot="",
            )
            db.commit()
            self.assertIn("负责人：任务负责人", notification.content_snapshot)
            self.assertIn("任务创建人：系统管理员", notification.content_snapshot)
            self.assertIn("主任务详情：主任务正文说明", notification.content_snapshot)
            self.assertIn("主任务备注：主任务备注说明", notification.content_snapshot)
            self.assertEqual(notification.notify_type, "task_created")
            recipient_record = (
                db.query(NotificationRecipient)
                .filter(NotificationRecipient.notification_id == notification.id, NotificationRecipient.user_id == 3)
                .first()
            )
            self.assertIsNotNone(recipient_record)
            self.assertIn("整理测试子任务", recipient_record.content_snapshot)
            self.assertIn("任务创建人：系统管理员", recipient_record.content_snapshot)
            self.assertIn("负责人：任务负责人", recipient_record.content_snapshot)
            self.assertIn("当前提醒重点：主任务整体进度跟进", recipient_record.content_snapshot)

    def test_preview_notification_content_returns_correct_context(self) -> None:
        """预览链路应与真实发送链路保持一致，方便管理员直接排查占位符问题。"""
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.title == "链路测试任务").first()
            recipient = db.query(User).filter(User.username == "member").first()
            preview = preview_notification_content(
                db=db,
                task=task,
                channel="email",
                notify_type="task_created",
                recipient=recipient,
            )
            self.assertEqual(preview["template_name"], "默认邮件发送模板")
            self.assertIn("任务创建人：系统管理员", preview["content"])
            self.assertIn("负责人：任务负责人", preview["content"])
            self.assertIn("主任务详情：主任务正文说明", preview["content"])
            self.assertIn("主任务备注：主任务备注说明", preview["content"])
            self.assertIn("整理测试子任务", preview["content"])
            self.assertEqual(preview["context"]["recipient_name"], "默认成员")
            self.assertEqual(preview["context"]["owner_name"], "任务负责人")
            self.assertEqual(preview["context"]["creator_name"], "系统管理员")
            self.assertEqual(preview["context"]["task_remark"], "主任务备注说明")
            self.assertEqual(preview["context"]["remind_focus"], "主任务整体进度跟进")

    def test_preview_uses_database_rows_instead_of_task_relationship_cache(self) -> None:
        """创建任务瞬间即使关系缓存还没挂到 task 对象上，也要能渲染出负责人和子任务。"""
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            member = db.query(User).filter(User.username == "member").first()
            task = Task(
                title="缓存测试任务",
                content="测试创建瞬间预览",
                priority="medium",
                remark="",
                start_at=datetime(2026, 4, 23, 9, 0, 0),
                end_at=datetime(2026, 4, 30, 18, 0, 0),
                planned_minutes=7 * 24 * 60,
                due_remind_days=1,
                created_by=admin.id,
            )
            db.add(task)
            db.flush()
            db.add(TaskMember(task_id=task.id, user_id=admin.id, member_role="owner"))
            db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="participant"))
            db.add(
                TaskSubtask(
                    task_id=task.id,
                    title="创建瞬间子任务",
                    content="需要立即出现在预览中。",
                    assignee_id=member.id,
                    sort_order=0,
                )
            )
            preview = preview_notification_content(
                db=db,
                task=task,
                channel="email",
                notify_type="task_created",
                recipient=member,
            )
            self.assertIn("负责人：系统管理员", preview["content"])
            self.assertIn("创建瞬间子任务", preview["content"])
            db.rollback()


if __name__ == "__main__":
    unittest.main()
