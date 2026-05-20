from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_task_create.db"

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Task, User
from app.security import hash_password


class TaskCreateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            db.add_all(
                [
                    User(
                        username="admin",
                        password_hash=hash_password("ChangeMe123"),
                        role="admin",
                        name="系统管理员",
                        email="admin@example.com",
                        ip_address="10.0.0.1",
                        is_active=True,
                    ),
                    User(
                        username="member",
                        password_hash=hash_password("ChangeMe123"),
                        role="member",
                        name="默认成员",
                        email="member@example.com",
                        ip_address="10.0.0.2",
                        is_active=True,
                    ),
                ]
            )
            db.commit()

    def test_create_task_should_not_raise_owner_member_name_error(self) -> None:
        end_at = datetime.now() + timedelta(days=2)
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe123"})
            self.assertEqual(login_response.status_code, 200)
            token = login_response.json()["access_token"]

            response = client.post(
                "/api/v1/tasks",
                json={
                    "title": "创建任务接口回归测试",
                    "content": "验证 owner_member 未定义问题已经修复。",
                    "owner_id": 1,
                    "participant_ids": [2],
                    "start_at": "2026-05-01T09:00:00",
                    "end_at": end_at.isoformat(timespec="seconds"),
                    "priority": "high",
                    "remark": "测试备注",
                    "due_remind_days": 1,
                    "milestones": [],
                    "subtasks": [],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["title"], "创建任务接口回归测试")
            self.assertEqual(payload["owner_name"], "系统管理员")

        with SessionLocal() as db:
            task = db.query(Task).filter(Task.title == "创建任务接口回归测试").first()
            self.assertIsNotNone(task)

    def test_create_task_keeps_not_started_until_qax_read(self) -> None:
        """Web 创建任务使用服务端创建时间作为开始时间，并保持未开始直到 QAX 已读。"""
        request_started_at = datetime.now()
        end_at = request_started_at + timedelta(days=2)
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe123"})
            self.assertEqual(login_response.status_code, 200)
            token = login_response.json()["access_token"]

            response = client.post(
                "/api/v1/tasks",
                json={
                    "title": "time should not start task",
                    "content": "start_at is in the past but status must stay not_started",
                    "owner_id": 1,
                    "participant_ids": [2],
                    "start_at": "2000-01-01T09:00:00",
                    "end_at": end_at.isoformat(timespec="seconds"),
                    "priority": "high",
                    "remark": "",
                    "due_remind_days": 1,
                    "milestones": [],
                    "subtasks": [],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["main_status"], "not_started")
            self.assertIsNone(payload["completed_at"])
            response_started_at = datetime.fromisoformat(payload["start_at"])
            self.assertGreaterEqual(response_started_at, request_started_at - timedelta(seconds=2))
            self.assertLessEqual(response_started_at, datetime.now() + timedelta(seconds=2))

        with SessionLocal() as db:
            task = db.query(Task).filter(Task.title == "time should not start task").first()
            self.assertIsNotNone(task)
            self.assertEqual(task.main_status, "not_started")
            self.assertIsNone(task.completed_at)
            self.assertGreaterEqual(task.start_at, request_started_at - timedelta(seconds=2))
            self.assertLessEqual(task.start_at, datetime.now() + timedelta(seconds=2))


if __name__ == "__main__":
    unittest.main()
