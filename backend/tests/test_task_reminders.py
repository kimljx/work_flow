from __future__ import annotations

import os
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///./test_task_reminders.db"

from app.api import remind_task_milestone, remind_task_subtask
from app.bootstrap import DEFAULT_TEMPLATES
from app.db import Base, SessionLocal, engine
from app.api import serialize_notification_detail
from app.models import Notification, NotificationRecipient, Task, TaskMember, TaskMilestone, TaskSubtask, Template, User
from app.security import hash_password


class TaskReminderApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            admin = User(
                username="admin",
                password_hash=hash_password("ChangeMe123"),
                role="admin",
                name="系统管理员",
                email="admin@example.com",
                ip_address="10.0.0.1",
                is_active=True,
            )
            owner = User(
                username="owner",
                password_hash=hash_password("ChangeMe123"),
                role="member",
                name="任务负责人",
                email="owner@example.com",
                ip_address="10.0.0.2",
                is_active=True,
            )
            member = User(
                username="member",
                password_hash=hash_password("ChangeMe123"),
                role="member",
                name="默认成员",
                email="member@example.com",
                ip_address="10.0.0.3",
                is_active=True,
            )
            db.add_all([admin, owner, member])
            db.flush()

            task = Task(
                title="提醒测试任务",
                content="请按节点推进主任务",
                priority="high",
                remark="测试提醒聚焦内容",
                start_at=datetime(2026, 4, 27, 9, 0, 0),
                end_at=datetime(2026, 4, 30, 18, 0, 0),
                planned_minutes=4 * 24 * 60,
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
                    title="整理数据",
                    content="汇总本周数据并校验",
                    assignee_id=member.id,
                    sort_order=0,
                )
            )
            db.add(
                TaskMilestone(
                    task_id=task.id,
                    name="正式提交",
                    planned_at=datetime(2026, 4, 29, 18, 0, 0),
                    remind_offsets="1,3",
                    sort_order=0,
                    status="pending",
                )
            )
            for item in DEFAULT_TEMPLATES:
                db.add(Template(**item))
            db.commit()

    def test_subtask_remind_targets_assignee_and_includes_focus(self) -> None:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            response = remind_task_subtask(1, 1, current_user=admin, db=db)
            self.assertEqual(response.message, "已向子任务执行人发送提醒")

            notification = db.query(Notification).order_by(Notification.id.asc()).first()
            self.assertIsNotNone(notification)
            recipient_records = (
                db.query(NotificationRecipient)
                .filter(NotificationRecipient.notification_id == notification.id)
                .all()
            )
            self.assertEqual(len(recipient_records), 1)
            self.assertIn("当前提醒重点：请优先跟进子任务“整理数据”", recipient_records[0].content_snapshot)
            self.assertIn("主任务备注：测试提醒聚焦内容", recipient_records[0].content_snapshot)
            detail = serialize_notification_detail(notification, db)
            self.assertEqual(detail.notify_scene_text, "子任务提醒")
            self.assertEqual(detail.remind_focus, "请优先跟进子任务“整理数据”")

    def test_milestone_remind_includes_milestone_focus(self) -> None:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            response = remind_task_milestone(1, 1, current_user=admin, db=db)
            self.assertEqual(response.message, "已向任务成员发送里程碑提醒")

            notification = db.query(Notification).order_by(Notification.id.asc()).first()
            self.assertIsNotNone(notification)
            recipient_records = (
                db.query(NotificationRecipient)
                .filter(NotificationRecipient.notification_id == notification.id)
                .all()
            )
            self.assertGreaterEqual(len(recipient_records), 2)
            self.assertIn("当前提醒重点：请围绕里程碑“正式提交”推进", notification.content_snapshot)
            detail = serialize_notification_detail(notification, db)
            self.assertEqual(detail.notify_scene_text, "里程碑提醒")
            self.assertTrue(detail.remind_focus.startswith("请围绕里程碑“正式提交”推进"))


if __name__ == "__main__":
    unittest.main()
