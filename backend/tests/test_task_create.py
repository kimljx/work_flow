from __future__ import annotations

import os
import time
import unittest
from datetime import datetime, timedelta
from threading import Event
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///./test_task_create.db"

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Task, User
from app.security import hash_password


class TaskCreateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.enqueue_patcher = patch("app.api._enqueue_task_created_notifications", return_value=None)
        self.enqueue_mock = self.enqueue_patcher.start()
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

    def tearDown(self) -> None:
        if self.enqueue_patcher is not None:
            self.enqueue_patcher.stop()

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
            self.enqueue_mock.assert_called_once()

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

    def test_create_task_returns_before_slow_notifications(self) -> None:
        """创建接口不等待邮件和即时消息发送完成，避免前端卡在提交界面。"""
        self.enqueue_patcher.stop()
        self.enqueue_patcher = None
        started = Event()
        finished = Event()

        def slow_background_runner(task_id: int) -> None:
            started.set()
            time.sleep(1.2)
            finished.set()

        end_at = datetime.now() + timedelta(days=2)
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "ChangeMe123"})
            self.assertEqual(login_response.status_code, 200)
            token = login_response.json()["access_token"]

            with patch("app.api._run_task_created_notifications", side_effect=slow_background_runner):
                request_started = time.perf_counter()
                response = client.post(
                    "/api/v1/tasks",
                    json={
                        "title": "后台通知不阻塞创建",
                        "content": "验证创建任务先返回，通知发送进入后台线程。",
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
                elapsed = time.perf_counter() - request_started

                self.assertEqual(response.status_code, 200)
                self.assertLess(elapsed, 0.8)
                self.assertTrue(started.wait(2))
                self.assertTrue(finished.wait(2))


if __name__ == "__main__":
    unittest.main()
