from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_users.db"

from fastapi import HTTPException

from app.constants import ADMIN_ROLES
from app.bootstrap import bootstrap_database
from app.db import Base, SessionLocal, engine
from app.models import AuditLog, MailAction, MailEvent, Notification, NotificationRecipient, Task, Template, User
from app.api import bulk_delete_mail_events, bulk_delete_notifications, cleanup_task_scheduled_notifications, delete_mail_event, delete_notification, delete_template
from app.schemas import MailEventBulkDeleteRequest, NotificationBulkDeleteRequest
from app.services.users import ensure_last_admin_not_removed


class UserProtectionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            db.add(User(username="admin", password_hash="x", role="system_admin", name="Admin", email="admin@test.local", ip_address="1.1.1.1", is_active=True))
            db.commit()

    def test_last_admin_role_cannot_be_disabled(self) -> None:
        """最后一个启用的管理角色账号不允许被禁用或降级。"""
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == "admin").first()
            self.assertIsNotNone(user)
            with self.assertRaises(HTTPException):
                ensure_last_admin_not_removed(db, user, new_role="member", new_active=False)

    def test_admin_can_be_downgraded_when_another_admin_role_exists(self) -> None:
        """系统中仍有其他管理角色时，普通管理员可以调整为成员。"""
        with SessionLocal() as db:
            db.add(User(username="ops", password_hash="x", role="admin", name="Ops", email="ops@test.local", ip_address="1.1.1.2", is_active=True))
            db.commit()
            user = db.query(User).filter(User.username == "ops").first()
            self.assertIsNotNone(user)
            ensure_last_admin_not_removed(db, user, new_role="member", new_active=True)
            self.assertIn("system_admin", ADMIN_ROLES)

    def test_cleanup_task_scheduled_notifications_removes_due_reminders(self) -> None:
        """删除任务前会清理任务相关到期提醒通知和接收人明细。"""
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            task = Task(
                title="待删除任务",
                content="内容",
                start_at=datetime(2026, 4, 27, 9, 0, 0),
                end_at=datetime(2026, 4, 28, 18, 0, 0),
                created_by=admin.id,
                due_remind_days=1,
            )
            db.add(task)
            db.flush()
            notification = Notification(task_id=task.id, channel="email", notify_type="due_remind", content_snapshot="提醒内容", status="pending")
            db.add(notification)
            db.flush()
            db.add(NotificationRecipient(notification_id=notification.id, user_id=admin.id, recipient_role="admin"))
            db.commit()

            cleaned_count = cleanup_task_scheduled_notifications(db, task.id)

            self.assertEqual(cleaned_count, 1)
            self.assertEqual(db.query(Notification).count(), 0)
            self.assertEqual(db.query(NotificationRecipient).count(), 0)

    def test_delete_notification_removes_recipients_and_writes_log(self) -> None:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            notification = Notification(task_id=None, channel="email", notify_type="manual_remind", content_snapshot="提醒内容", status="delivered")
            db.add(notification)
            db.flush()
            db.add(NotificationRecipient(notification_id=notification.id, user_id=admin.id, recipient_role="admin"))
            db.commit()

            message = delete_notification(notification.id, current_user=admin, db=db)

            self.assertIn("已删除", message.message)
            self.assertEqual(db.query(Notification).count(), 0)
            self.assertEqual(db.query(NotificationRecipient).count(), 0)
            self.assertEqual(db.query(AuditLog).filter(AuditLog.action_type == "DELETE_NOTIFICATION").count(), 1)

    def test_bulk_delete_notifications_removes_selected_records(self) -> None:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            first = Notification(task_id=None, channel="email", notify_type="manual_remind", content_snapshot="提醒1", status="delivered")
            second = Notification(task_id=None, channel="qax", notify_type="manual_remind", content_snapshot="提醒2", status="delivered")
            db.add_all([first, second])
            db.flush()
            db.add_all(
                [
                    NotificationRecipient(notification_id=first.id, user_id=admin.id, recipient_role="admin"),
                    NotificationRecipient(notification_id=second.id, user_id=admin.id, recipient_role="admin"),
                ]
            )
            db.commit()

            message = bulk_delete_notifications(NotificationBulkDeleteRequest(ids=[first.id, second.id]), current_user=admin, db=db)

            self.assertIn("2", message.message)
            self.assertEqual(db.query(Notification).count(), 0)
            self.assertEqual(db.query(NotificationRecipient).count(), 0)
            self.assertEqual(db.query(AuditLog).filter(AuditLog.action_type == "BULK_DELETE_NOTIFICATION").count(), 1)

    def test_delete_template_clears_mail_event_reference(self) -> None:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            template = Template(
                name="可删除模板",
                template_kind="MAIL_REPLY",
                notify_type="task_done",
                priority=100,
                version=1,
                enabled=True,
                is_default=False,
                subject_rule="完成",
                body_rule="完成",
                content="测试",
            )
            db.add(template)
            db.flush()
            event = MailEvent(
                message_id="<template-ref@example.com>",
                from_addr="member@test.local",
                subject="已完成",
                body_digest="已完成",
                original_body="已完成",
                resolved_template_id=template.id,
                process_status="MATCHED",
            )
            db.add(event)
            db.commit()

            message = delete_template(template.id, current_user=admin, db=db)
            db.refresh(event)

            self.assertIn("已删除", message.message)
            self.assertIsNone(event.resolved_template_id)
            self.assertEqual(db.query(Template).count(), 0)

    def test_bootstrap_deletes_mail_events_referencing_deprecated_delay_templates(self) -> None:
        """启动清理旧延期模板时，同步删除引用旧模板的历史收件记录。"""
        with SessionLocal() as db:
            template = Template(
                name="旧延期模板",
                template_kind="MAIL_REPLY",
                notify_type="delay_request",
                priority=1,
                version=1,
                enabled=True,
                is_default=True,
                subject_rule="延期",
                body_rule="延期",
                content="旧延期模板",
            )
            db.add(template)
            db.flush()
            event = MailEvent(
                message_id="<delay-request@example.com>",
                from_addr="member@test.local",
                subject="延期申请",
                body_digest="延期",
                original_body="延期",
                process_status="MATCHED",
                resolved_template_id=template.id,
            )
            db.add(event)
            db.flush()
            db.add(MailAction(mail_event_id=event.id, action_type="delay_request", action_status="APPLIED", action_result_json="{}"))
            db.commit()

        bootstrap_database()

        with SessionLocal() as db:
            self.assertIsNone(db.query(Template).filter(Template.notify_type == "delay_request").first())
            self.assertEqual(db.query(MailEvent).filter(MailEvent.message_id == "<delay-request@example.com>").count(), 0)
            self.assertEqual(db.query(MailAction).count(), 0)

    def test_delete_mail_event_removes_actions_and_writes_log(self) -> None:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            event = MailEvent(message_id="<delete-mail@example.com>", from_addr="member@test.local", subject="已完成", body_digest="已完成", original_body="已完成", process_status="MATCHED")
            db.add(event)
            db.flush()
            db.add(MailAction(mail_event_id=event.id, action_type="task_done", action_status="APPLIED", action_result_json="{}"))
            db.commit()

            message = delete_mail_event(event.id, current_user=admin, db=db)

            self.assertIn("已删除", message.message)
            self.assertEqual(db.query(MailEvent).count(), 0)
            self.assertEqual(db.query(MailAction).count(), 0)
            self.assertEqual(db.query(AuditLog).filter(AuditLog.action_type == "DELETE_MAIL_EVENT").count(), 1)

    def test_bulk_delete_mail_events_removes_selected_records(self) -> None:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            first = MailEvent(message_id="<bulk-mail-1@example.com>", from_addr="member@test.local", subject="已完成", body_digest="已完成", original_body="已完成", process_status="MATCHED")
            second = MailEvent(message_id="<bulk-mail-2@example.com>", from_addr="member@test.local", subject="进行中", body_digest="进行中", original_body="进行中", process_status="MATCHED")
            db.add_all([first, second])
            db.flush()
            db.add_all(
                [
                    MailAction(mail_event_id=first.id, action_type="task_done", action_status="APPLIED", action_result_json="{}"),
                    MailAction(mail_event_id=second.id, action_type="task_in_progress", action_status="APPLIED", action_result_json="{}"),
                ]
            )
            db.commit()

            message = bulk_delete_mail_events(MailEventBulkDeleteRequest(ids=[first.id, second.id]), current_user=admin, db=db)

            self.assertIn("2", message.message)
            self.assertEqual(db.query(MailEvent).count(), 0)
            self.assertEqual(db.query(MailAction).count(), 0)
            self.assertEqual(db.query(AuditLog).filter(AuditLog.action_type == "BULK_DELETE_MAIL_EVENT").count(), 1)


if __name__ == "__main__":
    unittest.main()
