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
from app.models import MailAction, MailEvent, Task, User
from app.security import hash_password

LOGIN_PASSWORD = hash_password("ChangeMe123")


class TaskCreateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.enqueue_patcher = patch("app.api._enqueue_task_created_notifications", return_value=None)
        self.enqueue_mock = self.enqueue_patcher.start()
        self.update_enqueue_patcher = patch("app.api._enqueue_task_update_notifications", return_value=None)
        self.update_enqueue_mock = self.update_enqueue_patcher.start()
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
                    User(
                        username="member2",
                        password_hash=hash_password("ChangeMe123"),
                        role="member",
                        name="新增成员",
                        email="member2@example.com",
                        ip_address="10.0.0.3",
                        is_active=True,
                    ),
                ]
            )
            db.commit()

    def tearDown(self) -> None:
        if self.enqueue_patcher is not None:
            self.enqueue_patcher.stop()
        if self.update_enqueue_patcher is not None:
            self.update_enqueue_patcher.stop()

    def test_create_task_should_not_raise_owner_member_name_error(self) -> None:
        end_at = datetime.now() + timedelta(days=2)
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": LOGIN_PASSWORD})
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
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": LOGIN_PASSWORD})
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

    def test_task_detail_returns_latest_reply_without_quoted_original_mail(self) -> None:
        end_at = datetime.now() + timedelta(days=2)
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": LOGIN_PASSWORD})
            self.assertEqual(login_response.status_code, 200)
            headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            create_response = client.post(
                "/api/v1/tasks",
                json={
                    "title": "邮件回复详情展示",
                    "content": "验证最近回复正文",
                    "owner_id": 1,
                    "participant_ids": [2],
                    "start_at": "2026-05-01T09:00:00",
                    "end_at": end_at.isoformat(timespec="seconds"),
                    "priority": "medium",
                    "remark": "",
                    "due_remind_days": 0,
                    "milestones": [],
                    "subtasks": [{"title": "成员子任务", "content": "", "assignee_id": 2, "sort_order": 1, "status": "done"}],
                },
                headers=headers,
            )
            self.assertEqual(create_response.status_code, 200)
            task_id = create_response.json()["id"]

            with SessionLocal() as db:
                event = MailEvent(
                    message_id="<latest-reply@example.com>",
                    from_addr="默认成员 <member@example.com>",
                    subject=f"回复：【任务通知#{task_id}】邮件回复详情展示",
                    body_digest="已完成\n处理结果已提交",
                    original_body="已完成\n处理结果已提交\n\n-----Original Message-----\n任务内容不应展示",
                    process_status="APPLIED",
                )
                db.add(event)
                db.flush()
                db.add(
                    MailAction(
                        mail_event_id=event.id,
                        action_type="task_done",
                        target_task_id=task_id,
                        action_status="APPLIED",
                        action_result_json="{}",
                    )
                )
                db.commit()

            detail_response = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
            self.assertEqual(detail_response.status_code, 200)
            member = next(item for item in detail_response.json()["members"] if item["user_id"] == 2)
            self.assertEqual(member["latest_mail_reply"]["content"], "已完成\n处理结果已提交")

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
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": LOGIN_PASSWORD})
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

    def test_update_task_subtask_change_notifies_only_assignee(self) -> None:
        """只修改某个成员的子任务时，只给该成员发送任务更新通知。"""
        end_at = datetime.now() + timedelta(days=2)
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": LOGIN_PASSWORD})
            self.assertEqual(login_response.status_code, 200)
            token = login_response.json()["access_token"]

            create_response = client.post(
                "/api/v1/tasks",
                json={
                    "title": "子任务定向通知",
                    "content": "主任务内容保持不变",
                    "owner_id": 1,
                    "participant_ids": [2],
                    "start_at": "2000-01-01T09:00:00",
                    "end_at": end_at.isoformat(timespec="seconds"),
                    "priority": "medium",
                    "remark": "",
                    "due_remind_days": 1,
                    "milestones": [],
                    "subtasks": [{"title": "旧子任务", "content": "旧内容", "assignee_id": 2, "sort_order": 1, "status": "pending"}],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(create_response.status_code, 200)
            task_payload = create_response.json()
            self.update_enqueue_mock.reset_mock()

            update_response = client.put(
                f"/api/v1/tasks/{task_payload['id']}",
                json={
                    "title": task_payload["title"],
                    "content": task_payload["content"],
                    "owner_id": 1,
                    "participant_ids": [2],
                    "start_at": task_payload["start_at"],
                    "end_at": task_payload["end_at"],
                    "priority": task_payload["priority"],
                    "remark": task_payload["remark"],
                    "due_remind_days": task_payload["due_remind_days"],
                    "milestones": [],
                    "subtasks": [{"title": "新子任务", "content": "新内容", "assignee_id": 2, "sort_order": 1, "status": "pending"}],
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            self.assertEqual(update_response.status_code, 200)
            self.update_enqueue_mock.assert_called_once()
            _, recipient_updates = self.update_enqueue_mock.call_args.args
            self.assertEqual([item["user_id"] for item in recipient_updates], [2])
            self.assertIn("子任务", recipient_updates[0]["summary"])

    def test_update_task_add_member_notifies_only_added_member(self) -> None:
        """只新增参与人时，不打扰原负责人和原参与人。"""
        end_at = datetime.now() + timedelta(days=2)
        with TestClient(app) as client:
            login_response = client.post("/api/v1/auth/login", json={"username": "admin", "password": LOGIN_PASSWORD})
            self.assertEqual(login_response.status_code, 200)
            token = login_response.json()["access_token"]

            create_response = client.post(
                "/api/v1/tasks",
                json={
                    "title": "新增成员定向通知",
                    "content": "主任务内容保持不变",
                    "owner_id": 1,
                    "participant_ids": [2],
                    "start_at": "2000-01-01T09:00:00",
                    "end_at": end_at.isoformat(timespec="seconds"),
                    "priority": "medium",
                    "remark": "",
                    "due_remind_days": 1,
                    "milestones": [],
                    "subtasks": [],
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(create_response.status_code, 200)
            task_payload = create_response.json()
            self.update_enqueue_mock.reset_mock()

            update_response = client.put(
                f"/api/v1/tasks/{task_payload['id']}",
                json={
                    "title": task_payload["title"],
                    "content": task_payload["content"],
                    "owner_id": 1,
                    "participant_ids": [2, 3],
                    "start_at": task_payload["start_at"],
                    "end_at": task_payload["end_at"],
                    "priority": task_payload["priority"],
                    "remark": task_payload["remark"],
                    "due_remind_days": task_payload["due_remind_days"],
                    "milestones": [],
                    "subtasks": [],
                },
                headers={"Authorization": f"Bearer {token}"},
            )

            self.assertEqual(update_response.status_code, 200)
            self.update_enqueue_mock.assert_called_once()
            _, recipient_updates = self.update_enqueue_mock.call_args.args
            self.assertEqual([item["user_id"] for item in recipient_updates], [3])
            self.assertIn("加入", recipient_updates[0]["summary"])


if __name__ == "__main__":
    unittest.main()
