from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_users.db"

from fastapi import HTTPException

from app.constants import ADMIN_ROLES
from app.db import Base, SessionLocal, engine
from app.models import Notification, NotificationRecipient, Task, User
from app.api import cleanup_task_scheduled_notifications
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


if __name__ == "__main__":
    unittest.main()
