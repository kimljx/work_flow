from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_notification_chain.db"

from app.bootstrap import DEFAULT_TEMPLATES
from app.db import Base, SessionLocal, engine
from app.models import Task, TaskMember, Template, User
from app.services.notifications import create_notification_with_recipients


class NotificationChainTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            admin = User(
                username="admin",
                password_hash="x",
                role="admin",
                name="管理员",
                email="admin@example.com",
                ip_address="10.0.0.1",
                is_active=True,
            )
            member = User(
                username="member",
                password_hash="x",
                role="member",
                name="成员",
                email="member@example.com",
                ip_address="10.0.0.2",
                is_active=True,
            )
            db.add_all([admin, member])
            db.flush()
            task = Task(
                title="链路测试任务",
                content="测试",
                priority="medium",
                remark="",
                start_at=datetime(2026, 4, 1, 0, 0, 0),
                end_at=datetime(2026, 4, 2, 0, 0, 0),
                planned_minutes=24 * 60,
                due_remind_days=1,
                created_by=admin.id,
            )
            db.add(task)
            db.flush()
            db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="participant"))
            for item in DEFAULT_TEMPLATES:
                db.add(Template(**item))
            db.commit()

    def test_outbound_notify_types_have_default_templates(self) -> None:
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

    def test_notification_creation_uses_template_content(self) -> None:
        with SessionLocal() as db:
            notification = create_notification_with_recipients(
                db=db,
                task_id=1,
                channel="qax",
                notify_type="task_created",
                content_snapshot="",
            )
            db.commit()
            self.assertIn("任务编号：1", notification.content_snapshot)
            self.assertIn("任务名称：链路测试任务", notification.content_snapshot)


if __name__ == "__main__":
    unittest.main()
