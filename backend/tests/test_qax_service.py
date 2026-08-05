from __future__ import annotations

import os
import subprocess
from pathlib import Path
import tempfile
import unittest
import asyncio
from datetime import datetime
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///./test_qax_service.db"

from app.db import Base, SessionLocal, engine
from app.models import Notification, NotificationRecipient, Task, TaskMember, Template, User
from app.services.notifications import create_notification_with_recipients
from app.services.qax import (
    QaxAutomationClient,
    QaxAutomationError,
    QaxTaskStatus,
    _build_qax_certificate_hint,
    _check_chromium_runtime_dependencies,
    _ensure_qax_runtime_directories,
    _local_chromium_executable,
    _map_qax_status,
    _validate_qax_certificates,
    _wrap_qax_startup_error,
    collect_qax_status,
    delete_qax_task_notifications,
    sanitize_qax_content,
)


class _FakeQaxAutomationClient:
    """用于测试 QAX 采集闭环的桩客户端。"""

    deleted_task_names: list[str]

    def __init__(self) -> None:
        self.deleted_task_names = []

    async def __aenter__(self) -> "_FakeQaxAutomationClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def query_task_status(self, task_name: str) -> QaxTaskStatus:
        return QaxTaskStatus(
            task_name=task_name,
            found=True,
            row_text="执行结束 已读",
            delivery_status="delivered",
            read_status="read",
            read_at="2026-07-30 11:30:00",
            detail="执行结束，终端已读",
        )

    async def delete_task_if_exists(self, task_name: str) -> bool:
        self.deleted_task_names.append(task_name)
        return True


class _UnreadQaxAutomationClient(_FakeQaxAutomationClient):
    """用于验证 QAX 送达但未读时，不应推进任务主状态。"""

    async def query_task_status(self, task_name: str) -> QaxTaskStatus:
        return QaxTaskStatus(
            task_name=task_name,
            found=True,
            row_text="执行结束 未读",
            delivery_status="delivered",
            read_status="unread",
            detail="执行结束，终端未读",
        )


class QaxServiceTestCase(unittest.TestCase):
    """覆盖 QAX 发送正文清洗与状态回写关键行为。"""

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            admin = User(
                username="admin",
                password_hash="x",
                role="system_admin",
                name="系统管理员",
                email="admin@example.com",
                ip_address="10.0.0.1",
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
            db.add_all([admin, member])
            db.flush()

            task = Task(
                title="QAX 链路测试任务",
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
            db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="participant"))
            db.add(
                Template(
                    name="QAX 测试模板",
                    template_kind="QAX_SEND",
                    notify_type="task_created",
                    priority=100,
                    version=1,
                    enabled=True,
                    is_default=True,
                    subject_rule="",
                    body_rule="",
                    content=(
                        "任务标题：{task_title}\n"
                        "任务详情：{task_content}\n"
                        "回复指引：\n"
                        "1. 请按“任务ID + 状态关键词”回复。\n"
                        "2. 如需延期请走邮件。\n"
                    ),
                )
            )
            db.commit()

    def tearDown(self) -> None:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists("test_qax_service.db"):
            os.remove("test_qax_service.db")

    def test_sanitize_qax_content_removes_reply_guide(self) -> None:
        """QAX 正文应自动移除邮件专属回复指引。"""
        content = (
            "任务标题：测试任务\n"
            "回复指引：\n"
            "1. 请按“任务ID + 状态关键词”回复。\n"
            "2. 如需延期请走邮件。\n"
            "任务详情：跟进内容\n"
        )
        sanitized = sanitize_qax_content(content)
        self.assertEqual(sanitized, "任务标题：测试任务\n任务详情：跟进内容")

    def test_map_qax_status_uses_row_for_delivery_and_detail_for_read(self) -> None:
        """QAX 列表状态表示是否发出，详情状态表示用户是否接收或确认。"""

        pending_status = _map_qax_status("task-a", row_text="准备中", detail_text="未接收")
        self.assertEqual(pending_status.delivery_status, "pending")
        self.assertEqual(pending_status.read_status, "unread")

        delivering_status = _map_qax_status("task-b", row_text="执行中", detail_text="正在执行")
        self.assertEqual(delivering_status.delivery_status, "pending")
        self.assertEqual(delivering_status.read_status, "unread")

        read_status = _map_qax_status("task-c", row_text="执行结束", detail_text="执行成功")
        self.assertEqual(read_status.delivery_status, "delivered")
        self.assertEqual(read_status.read_status, "read")

        canceled_status = _map_qax_status("task-d", row_text="已取消", detail_text="未接收")
        self.assertEqual(canceled_status.delivery_status, "failed")
        self.assertEqual(canceled_status.read_status, "unread")

        failed_status = _map_qax_status("task-e", row_text="执行结束", detail_text="执行失败")
        self.assertEqual(failed_status.delivery_status, "failed")
        self.assertEqual(failed_status.read_status, "unread")

    def test_query_task_status_falls_back_to_row_text_when_detail_popup_fails(self) -> None:
        class _FakeCell:
            async def inner_text(self) -> str:
                return "执行结束"

        class _FakeCells:
            def nth(self, index: int) -> _FakeCell:
                self.index = index
                return _FakeCell()

        class _FakeRowButton:
            async def click(self) -> None:
                raise RuntimeError("popup failed")

        class _FakeButtons:
            def nth(self, index: int) -> _FakeRowButton:
                self.index = index
                return _FakeRowButton()

        class _FakeRow:
            async def wait_for(self, *, state: str, timeout: int) -> None:
                return None

            def get_by_role(self, role: str):
                if role == "cell":
                    return _FakeCells()
                if role == "button":
                    return _FakeButtons()
                raise AssertionError(role)

        class _FakePopupContext:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            @property
            async def value(self):
                raise AssertionError("popup should not resolve when click fails")

        class _FakePage:
            def get_by_role(self, role: str, name: str | None = None):
                if role == "row":
                    return _FakeRow()
                raise AssertionError((role, name))

            def expect_popup(self) -> _FakePopupContext:
                return _FakePopupContext()

        client = QaxAutomationClient()
        client.page = _FakePage()

        result = asyncio.run(client.query_task_status("task-x", "10.0.0.2"))
        self.assertTrue(result.found)
        self.assertEqual(result.delivery_status, "delivered")
        self.assertEqual(result.read_status, "unread")
        self.assertEqual(result.detail, "执行结束\n执行结束")

    @patch("app.services.notifications.send_qax_notification")
    def test_create_notification_uses_sanitized_qax_content(self, mock_send_qax_notification) -> None:
        """创建 QAX 通知时，应发送并落库清洗后的正文快照。"""
        mock_send_qax_notification.return_value = {"status": "queued", "message": "QAX 即时消息任务已创建"}

        with SessionLocal() as db:
            notification = create_notification_with_recipients(
                db=db,
                task_id=1,
                channel="qax",
                notify_type="task_created",
                content_snapshot="",
            )
            db.commit()

            self.assertEqual(notification.content_snapshot, "任务标题：QAX 链路测试任务\n任务详情：主任务正文说明")
            recipient = db.query(NotificationRecipient).filter(NotificationRecipient.notification_id == notification.id).first()
            self.assertIsNotNone(recipient)
            self.assertEqual(recipient.content_snapshot, "任务标题：QAX 链路测试任务\n任务详情：主任务正文说明")
            mock_send_qax_notification.assert_called_once()
            sent_content = mock_send_qax_notification.call_args.kwargs["content"]
            self.assertEqual(sent_content, "任务标题：QAX 链路测试任务\n任务详情：主任务正文说明")

    def test_collect_qax_status_updates_recipient_feedback(self) -> None:
        """采集到 QAX 已读结果后，应回写接收人状态并刷新通知主状态。"""
        with SessionLocal() as db:
            notification = Notification(
                task_id=1,
                channel="qax",
                notify_type="task_created",
                content_snapshot="任务标题：QAX 链路测试任务",
                status="pending",
            )
            db.add(notification)
            db.flush()
            db.add(
                NotificationRecipient(
                    notification_id=notification.id,
                    user_id=2,
                    recipient_role="participant",
                    delivery_status="pending",
                    read_status="unread",
                    retry_count=0,
                    content_snapshot="任务标题：QAX 链路测试任务",
                    last_error="",
                )
            )
            db.commit()

            fake_client = _FakeQaxAutomationClient()
            with patch("app.services.qax._ensure_qax_settings", return_value=None), patch(
                "app.services.qax.QaxAutomationClient",
                return_value=fake_client,
            ):
                result = collect_qax_status(db)
                db.commit()

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["processed_count"], 1)
            self.assertEqual(result["updated_count"], 1)
            self.assertEqual(result["failed_count"], 0)
            recipient = db.query(NotificationRecipient).filter(NotificationRecipient.notification_id == notification.id).first()
            refreshed_notification = db.query(Notification).filter(Notification.id == notification.id).first()
            refreshed_task = db.query(Task).filter(Task.id == notification.task_id).first()
            self.assertEqual(recipient.delivery_status, "delivered")
            self.assertEqual(recipient.read_status, "read")
            self.assertEqual(recipient.read_at, "2026-07-30 11:30:00")
            self.assertEqual(recipient.last_error, "")
            self.assertEqual(refreshed_notification.status, "delivered")
            self.assertEqual(refreshed_task.main_status, "in_progress")
            self.assertEqual(len(fake_client.deleted_task_names), 1)

    def test_delete_qax_task_notifications_removes_every_recipient_task(self) -> None:
        with SessionLocal() as db:
            task = db.query(Task).filter(Task.id == 1).first()
            first = Notification(task_id=task.id, channel="qax", notify_type="task_created", content_snapshot="", status="delivered")
            second = Notification(task_id=task.id, channel="qax", notify_type="manual_remind", content_snapshot="", status="delivered")
            db.add_all([first, second])
            db.flush()
            db.add_all(
                [
                    NotificationRecipient(notification_id=first.id, user_id=2, recipient_role="participant"),
                    NotificationRecipient(notification_id=second.id, user_id=2, recipient_role="participant"),
                ]
            )
            db.commit()

            fake_client = _FakeQaxAutomationClient()
            with patch("app.services.qax._ensure_qax_settings", return_value=None), patch(
                "app.services.qax.QaxAutomationClient",
                return_value=fake_client,
            ):
                result = delete_qax_task_notifications(db, task)

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["attempted"], 2)
            self.assertEqual(result["deleted"], 2)
            self.assertEqual(result["failed"], 0)
            self.assertEqual(len(fake_client.deleted_task_names), 2)

    def test_collect_any_qax_read_starts_not_started_task(self) -> None:
        """未开始任务收到任意类型 QAX 已读反馈后，都应推进为进行中。"""
        with SessionLocal() as db:
            notification = Notification(
                task_id=1,
                channel="qax",
                notify_type="manual_remind",
                content_snapshot="手动提醒 QAX",
                status="pending",
            )
            db.add(notification)
            db.flush()
            db.add(
                NotificationRecipient(
                    notification_id=notification.id,
                    user_id=2,
                    recipient_role="participant",
                    delivery_status="pending",
                    read_status="unread",
                    retry_count=0,
                    content_snapshot="手动提醒 QAX",
                    last_error="",
                )
            )
            db.commit()

            fake_client = _FakeQaxAutomationClient()
            with patch("app.services.qax._ensure_qax_settings", return_value=None), patch(
                "app.services.qax.QaxAutomationClient",
                return_value=fake_client,
            ):
                result = collect_qax_status(db)
                db.commit()

            refreshed_task = db.query(Task).filter(Task.id == notification.task_id).first()
            self.assertEqual(result["status"], "success")
            self.assertEqual(refreshed_task.main_status, "in_progress")

    def test_collect_qax_delivered_but_unread_does_not_start_task(self) -> None:
        """只有任务创建即时消息已读才能将任务推进为进行中，单纯送达不能推进。"""
        with SessionLocal() as db:
            notification = Notification(
                task_id=1,
                channel="qax",
                notify_type="task_created",
                content_snapshot="任务标题：QAX 链路测试任务",
                status="pending",
            )
            db.add(notification)
            db.flush()
            db.add(
                NotificationRecipient(
                    notification_id=notification.id,
                    user_id=2,
                    recipient_role="participant",
                    delivery_status="pending",
                    read_status="unread",
                    retry_count=0,
                    content_snapshot="任务标题：QAX 链路测试任务",
                    last_error="",
                )
            )
            db.commit()

            fake_client = _UnreadQaxAutomationClient()
            with patch("app.services.qax._ensure_qax_settings", return_value=None), patch(
                "app.services.qax.QaxAutomationClient",
                return_value=fake_client,
            ):
                result = collect_qax_status(db)
                db.commit()

            recipient = db.query(NotificationRecipient).filter(NotificationRecipient.notification_id == notification.id).first()
            refreshed_task = db.query(Task).filter(Task.id == notification.task_id).first()
            self.assertEqual(result["status"], "success")
            self.assertEqual(recipient.delivery_status, "delivered")
            self.assertEqual(recipient.read_status, "unread")
            self.assertEqual(refreshed_task.main_status, "not_started")
            self.assertEqual(len(fake_client.deleted_task_names), 0)

    def test_build_qax_certificate_hint_uses_system_trust_store_guidance(self) -> None:
        state = _validate_qax_certificates()
        hint = _build_qax_certificate_hint(state)
        self.assertIn("系统级信任链", hint)
        self.assertIn("不会读取 config/", hint)

    def test_wrap_qax_startup_error_adds_certificate_guidance(self) -> None:
        state = _validate_qax_certificates()
        wrapped = _wrap_qax_startup_error(RuntimeError("net::ERR_BAD_SSL_CLIENT_AUTH_CERT"), state)
        self.assertIsInstance(wrapped, QaxAutomationError)
        self.assertIn("证书/TLS 错误", str(wrapped))
        self.assertIn("系统级信任链", str(wrapped))

    def test_wrap_qax_startup_error_mentions_glibc_browser_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_root = root / "config"
            config_root.mkdir()
            with patch("app.services.qax.PROJECT_ROOT", root):
                state = _validate_qax_certificates()
        wrapped = _wrap_qax_startup_error(RuntimeError("/lib64/libc.so.6: version `GLIBC_2.18' not found"), state)
        self.assertIsInstance(wrapped, QaxAutomationError)
        self.assertIn("重新打包", str(wrapped))

    def test_check_chromium_runtime_dependencies_reports_missing_libraries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "chrome"
            executable.write_text("binary", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                ["ldd", str(executable)],
                0,
                stdout="\tlibnss3.so => not found\n\tlibatk-1.0.so.0 => not found\n",
                stderr="",
            )

            with patch("app.services.qax.sys.platform", "linux"), patch(
                "app.services.qax.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaises(QaxAutomationError) as ctx:
                    _check_chromium_runtime_dependencies(str(executable))

            self.assertIn("libnss3.so", str(ctx.exception))
            self.assertIn("libatk-1.0.so.0", str(ctx.exception))

    def test_local_chromium_executable_supports_linux_bundle_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "chromium-1234" / "chrome-linux" / "chrome"
            executable.parent.mkdir(parents=True)
            executable.write_text("binary", encoding="utf-8")
            with patch.dict(os.environ, {"PLAYWRIGHT_BROWSERS_PATH": str(root)}, clear=False):
                resolved = _local_chromium_executable()
            self.assertEqual(resolved, str(executable))

    def test_ensure_qax_runtime_directories_creates_local_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("app.services.qax.PROJECT_ROOT", root):
                _ensure_qax_runtime_directories()

            self.assertTrue((root / "local" / "temp").is_dir())
            self.assertTrue((root / "local" / "cache").is_dir())
            self.assertTrue((root / "local" / "home").is_dir())
            self.assertTrue((root / "local" / "logs" / "qax_debug").is_dir())
            self.assertEqual(os.environ["TMPDIR"], str(root / "local" / "temp"))
            self.assertEqual(os.environ["HOME"], str(root / "local" / "home"))


if __name__ == "__main__":
    unittest.main()
