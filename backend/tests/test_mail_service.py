from __future__ import annotations

import base64
import socket
import ssl
import tempfile
import unittest
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from app import config as app_config
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import DelayRequest, MailAction, MailEvent, MailScanState, Notification, NotificationRecipient, Task, TaskMember, TaskSubtask, Template, User
from app.security import hash_password
from app.services.mail import (
    _build_mail_event_from_message,
    _delete_pop3_message,
    _mark_notification_recipient_replied,
    _extract_text_body,
    _find_task_id,
    _apply_task_status_from_mail,
    _patched_mail_dns_resolution,
    _plain_text_to_html,
    cleanup_applied_task_reply_mails,
    delete_task_related_mail_from_inbox,
    diagnose_imap_settings,
    diagnose_mail_settings,
    initialize_mail_scan_baseline,
    poll_mailbox,
    send_mail_notification,
)
from app.services import runtime_settings
from app.services.templates import strip_reply_guides


class MailServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_strip_reply_guides_removes_chinese_original_mail_separator(self) -> None:
        reply = "\u8fdb\u884c\u4e2d\uff0c\u5df2\u5b8c\u6210\u524d\u671f\u534f\u8c03\u5de5\u4f5c\u3002"
        original = "\u539f\u90ae\u4ef6\u4fe1\u606f"
        body = f"{reply}\n\n----------{original}----------\n\u5df2\u5b8c\u6210\n\u56de\u590d\u6307\u5f15"

        self.assertEqual(strip_reply_guides(body), reply)

    def test_strip_reply_guides_removes_dashed_mail_header_quote(self) -> None:
        reply = "\u8fdb\u884c\u4e2d\uff0c\u5df2\u5b8c\u6210\u524d\u671f\u534f\u8c03\u5de5\u4f5c\u3002"
        body = (
            f"{reply}\n\n-----------------\n\nmember@example.com\n\n"
            "\u53d1\u4ef6\u4eba\uff1asender\n\u53d1\u9001\u65f6\u95f4\uff1a2026-07-29 17:03\n"
            "\u6536\u4ef6\u4eba\uff1amember\n\u4e3b\u9898\uff1a\u3010\u4efb\u52a1\u901a\u77e5#10\u30111111"
        )

        self.assertEqual(strip_reply_guides(body), reply)
        self.assertEqual(strip_reply_guides(f"{reply}\n\u53d1\u4ef6\u4eba\uff1asender\n\u5df2\u5b8c\u6210"), reply)

    def test_patched_mail_dns_resolution_maps_domain_to_ip(self) -> None:
        import app.services.mail as mail_module

        with patch.object(mail_module, "_mail_host_ip_overrides", return_value={"smtp.example.com": "10.0.0.8"}), patch(
            "app.services.mail.socket.getaddrinfo"
        ) as mocked_getaddrinfo:
            mocked_getaddrinfo.return_value = []
            with _patched_mail_dns_resolution():
                socket.getaddrinfo("smtp.example.com", 25)

        mocked_getaddrinfo.assert_called_once()
        self.assertEqual(mocked_getaddrinfo.call_args.args[0], "10.0.0.8")
        self.assertEqual(mocked_getaddrinfo.call_args.args[1], 25)

    def test_send_mail_returns_reason_when_smtp_is_missing(self) -> None:
        original_host = settings.smtp_host
        original_from = settings.smtp_from_address
        settings.smtp_host = ""
        settings.smtp_from_address = ""
        try:
            result = send_mail_notification("member@test.local", "test", "body")
        finally:
            settings.smtp_host = original_host
            settings.smtp_from_address = original_from

        self.assertEqual(result["status"], "failed")
        self.assertIn("SMTP", result["message"])

    def test_port_465_uses_ssl_by_default(self) -> None:
        from app.services.mail import _make_zmail_smtp_server

        original_host = settings.smtp_host
        original_port = settings.smtp_port
        original_ssl = settings.smtp_use_ssl
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 465
        settings.smtp_use_ssl = False
        try:
            server = _make_zmail_smtp_server()
        finally:
            settings.smtp_host = original_host
            settings.smtp_port = original_port
            settings.smtp_use_ssl = original_ssl

        self.assertEqual(server.port, 465)
        self.assertTrue(server.ssl)

    def test_delete_pop3_message_sends_stat_before_dele(self) -> None:
        calls: list[tuple[str, int | None]] = []

        class FakePopServer:
            def __init__(self) -> None:
                self.server = self
                self.stat_called = False

            def __enter__(self) -> "FakePopServer":
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def stat(self) -> tuple[int, int]:
                self.stat_called = True
                calls.append(("stat", None))
                return (1, 100)

            def dele(self, message_number: int) -> None:
                if not self.stat_called:
                    raise RuntimeError("STAT first")
                calls.append(("dele", message_number))

        class FakeMailServer:
            def __init__(self) -> None:
                self.pop_server = FakePopServer()

        with patch("app.services.mail._make_zmail_mail_server", return_value=FakeMailServer()):
            _delete_pop3_message("INBOX", "16")

        self.assertEqual(calls, [("stat", None), ("dele", 16)])

    def test_diagnose_returns_dns_message_for_bad_host(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.smtp_host
        original_from = settings.smtp_from_address
        settings.smtp_host = "bad host"
        settings.smtp_from_address = "noreply@example.com"

        original_open = mail_module._open_smtp_connection

        def broken_open():
            raise socket.gaierror(11003, "getaddrinfo failed")

        mail_module._open_smtp_connection = broken_open
        try:
            result = diagnose_mail_settings()
        finally:
            mail_module._open_smtp_connection = original_open
            settings.smtp_host = original_host
            settings.smtp_from_address = original_from

        self.assertEqual(result["status"], "failed")
        self.assertIn("getaddrinfo failed", result["message"])

    def test_diagnose_returns_actionable_message_for_ssl_wrong_version(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.smtp_host
        original_from = settings.smtp_from_address
        original_port = settings.smtp_port
        original_ssl = settings.smtp_use_ssl
        original_tls = settings.smtp_use_tls
        original_open = mail_module._open_smtp_connection
        settings.smtp_host = "smtp.example.com"
        settings.smtp_from_address = "noreply@example.com"
        settings.smtp_port = 587
        settings.smtp_use_ssl = True
        settings.smtp_use_tls = False

        def broken_open():
            raise ssl.SSLError("[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1007)")

        mail_module._open_smtp_connection = broken_open
        try:
            result = diagnose_mail_settings()
        finally:
            mail_module._open_smtp_connection = original_open
            settings.smtp_host = original_host
            settings.smtp_from_address = original_from
            settings.smtp_port = original_port
            settings.smtp_use_ssl = original_ssl
            settings.smtp_use_tls = original_tls

        self.assertEqual(result["status"], "failed")
        self.assertIn("端口与加密方式不匹配", result["message"])
        self.assertIn("587 端口通常需要设置 SMTP_USE_TLS=true", result["message"])

    def test_send_mail_returns_actionable_message_for_ssl_wrong_version(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.smtp_host
        original_from = settings.smtp_from_address
        original_open = mail_module._open_smtp_connection
        settings.smtp_host = "smtp.example.com"
        settings.smtp_from_address = "noreply@example.com"

        def broken_open():
            raise ssl.SSLError("[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1007)")

        mail_module._open_smtp_connection = broken_open
        try:
            result = send_mail_notification("member@test.local", "主题", "正文")
        finally:
            mail_module._open_smtp_connection = original_open
            settings.smtp_host = original_host
            settings.smtp_from_address = original_from

        self.assertEqual(result["status"], "failed")
        self.assertIn("端口与加密方式不匹配", result["message"])

    def test_imap_requires_configuration(self) -> None:
        original_host = settings.imap_host
        original_user = settings.imap_user
        original_inbox_protocol = settings.mail_inbox_protocol
        settings.mail_inbox_protocol = "imap"
        settings.imap_host = ""
        settings.imap_user = ""
        try:
            result = diagnose_imap_settings()
        finally:
            settings.imap_host = original_host
            settings.imap_user = original_user
            settings.mail_inbox_protocol = original_inbox_protocol

        self.assertEqual(result["status"], "failed")
        self.assertIn("IMAP_HOST", result["message"])

    def test_diagnose_imap_supports_plain_connection(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.imap_host
        original_port = settings.imap_port
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_imap = mail_module.imaplib.IMAP4
        original_inbox_protocol = settings.mail_inbox_protocol
        settings.mail_inbox_protocol = "imap"
        settings.imap_host = "imap.example.com"
        settings.imap_port = 143
        settings.imap_user = "user"
        settings.imap_password = "pass"
        settings.imap_use_ssl = False
        settings.imap_use_tls = False

        class DummyImap:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, user, password):
                return "OK", []

            def select(self, mailbox):
                return "OK", []

        mail_module.imaplib.IMAP4 = lambda host, port: DummyImap()
        try:
            result = diagnose_imap_settings()
        finally:
            mail_module.imaplib.IMAP4 = original_imap
            settings.mail_inbox_protocol = original_inbox_protocol
            settings.imap_host = original_host
            settings.imap_port = original_port
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

        self.assertEqual(result["status"], "success")

    def test_diagnose_imap_selects_configured_folders(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.imap_host
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_inbox_protocol = settings.mail_inbox_protocol
        original_folders = settings.mail_inbox_folders
        original_open = mail_module._open_imap_connection
        selected: list[str] = []

        class DummyImap:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, user, password):
                return "OK", []

            def select(self, mailbox):
                selected.append(mailbox)
                return "OK", []

        settings.mail_inbox_protocol = "imap"
        settings.mail_inbox_folders = "INBOX,Replies"
        settings.imap_host = "imap.example.com"
        settings.imap_user = "user"
        settings.imap_password = "pass"
        settings.imap_use_ssl = True
        settings.imap_use_tls = False
        mail_module._open_imap_connection = lambda: DummyImap()
        try:
            result = diagnose_imap_settings()
        finally:
            mail_module._open_imap_connection = original_open
            settings.mail_inbox_protocol = original_inbox_protocol
            settings.mail_inbox_folders = original_folders
            settings.imap_host = original_host
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

        self.assertEqual(result["status"], "success")
        self.assertEqual(selected, ['"INBOX"', '"Replies"'])

    def test_diagnose_imap_returns_actionable_message_for_ssl_wrong_version(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.imap_host
        original_port = settings.imap_port
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_open = mail_module._open_imap_connection
        original_inbox_protocol = settings.mail_inbox_protocol
        settings.mail_inbox_protocol = "imap"
        settings.imap_host = "imap.example.com"
        settings.imap_port = 143
        settings.imap_user = "user"
        settings.imap_password = "pass"
        settings.imap_use_ssl = True
        settings.imap_use_tls = False

        def broken_open():
            raise ssl.SSLError("[SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1007)")

        mail_module._open_imap_connection = broken_open
        try:
            result = diagnose_imap_settings()
        finally:
            mail_module._open_imap_connection = original_open
            settings.mail_inbox_protocol = original_inbox_protocol
            settings.imap_host = original_host
            settings.imap_port = original_port
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

        self.assertEqual(result["status"], "failed")
        self.assertIn("端口与加密方式不匹配", result["message"])
        self.assertIn("143 端口通常需要设置 IMAP_USE_SSL=false", result["message"])

    def test_diagnose_pop3_supports_plain_connection(self) -> None:
        import app.services.mail as mail_module

        original_protocol = settings.mail_inbox_protocol
        original_host = settings.pop3_host
        original_port = settings.pop3_port
        original_user = settings.pop3_user
        original_password = settings.pop3_password
        original_ssl = settings.pop3_use_ssl
        original_tls = settings.pop3_use_tls
        original_factory = mail_module._make_zmail_mail_server

        class FakePOPServer:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeMailServer:
            pop_server = FakePOPServer()

        settings.mail_inbox_protocol = "pop3"
        settings.pop3_host = "pop3.example.com"
        settings.pop3_port = 110
        settings.pop3_user = "user"
        settings.pop3_password = "pass"
        settings.pop3_use_ssl = False
        settings.pop3_use_tls = False

        mail_module._make_zmail_mail_server = lambda u, p: FakeMailServer()
        try:
            result = diagnose_imap_settings()
        finally:
            mail_module._make_zmail_mail_server = original_factory
            settings.mail_inbox_protocol = original_protocol
            settings.pop3_host = original_host
            settings.pop3_port = original_port
            settings.pop3_user = original_user
            settings.pop3_password = original_password
            settings.pop3_use_ssl = original_ssl
            settings.pop3_use_tls = original_tls

        self.assertEqual(result["status"], "success")
        self.assertIn("POP3", result["message"])

    def test_diagnose_pop3_keeps_default_scan_when_folder_selection_is_unsupported(self) -> None:
        import app.services.mail as mail_module

        original_protocol = settings.mail_inbox_protocol
        original_host = settings.pop3_host
        original_port = settings.pop3_port
        original_user = settings.pop3_user
        original_password = settings.pop3_password
        original_ssl = settings.pop3_use_ssl
        original_tls = settings.pop3_use_tls
        original_folders = settings.mail_inbox_folders
        original_factory = mail_module._make_zmail_mail_server

        class FakePOPServer:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeMailServer:
            pop_server = FakePOPServer()

        settings.mail_inbox_protocol = "pop3"
        settings.mail_inbox_folders = "Replies"
        settings.pop3_host = "pop3.example.com"
        settings.pop3_port = 110
        settings.pop3_user = "user"
        settings.pop3_password = "pass"
        settings.pop3_use_ssl = False
        settings.pop3_use_tls = False
        mail_module._make_zmail_mail_server = lambda u, p: FakeMailServer()
        try:
            result = diagnose_imap_settings()
        finally:
            mail_module._make_zmail_mail_server = original_factory
            settings.mail_inbox_protocol = original_protocol
            settings.mail_inbox_folders = original_folders
            settings.pop3_host = original_host
            settings.pop3_port = original_port
            settings.pop3_user = original_user
            settings.pop3_password = original_password
            settings.pop3_use_ssl = original_ssl
            settings.pop3_use_tls = original_tls

        self.assertEqual(result["status"], "success")
        self.assertIn("POP3", result["message"])
        self.assertIn("Replies", result["message"])

    def test_diagnose_pop3_line_too_long_returns_configuration_hint(self) -> None:
        import app.services.mail as mail_module

        original_protocol = settings.mail_inbox_protocol
        original_host = settings.pop3_host
        original_port = settings.pop3_port
        original_user = settings.pop3_user
        original_password = settings.pop3_password
        original_ssl = settings.pop3_use_ssl
        original_tls = settings.pop3_use_tls
        original_factory = mail_module._make_zmail_mail_server
        settings.mail_inbox_protocol = "pop3"
        settings.pop3_host = "pop3.example.com"
        settings.pop3_port = 110
        settings.pop3_user = "user"
        settings.pop3_password = "pass"
        settings.pop3_use_ssl = False
        settings.pop3_use_tls = False

        def broken_factory(u: str, p: str):
            raise mail_module.poplib.error_proto("line too long")

        mail_module._make_zmail_mail_server = broken_factory
        try:
            result = diagnose_imap_settings()
        finally:
            mail_module._make_zmail_mail_server = original_factory
            settings.mail_inbox_protocol = original_protocol
            settings.pop3_host = original_host
            settings.pop3_port = original_port
            settings.pop3_user = original_user
            settings.pop3_password = original_password
            settings.pop3_use_ssl = original_ssl
            settings.pop3_use_tls = original_tls

        self.assertEqual(result["status"], "failed")
        self.assertIn("line too long", result["message"])
        self.assertIn("不是账号密码错误", result["message"])
        self.assertIn("POP3_HOST、POP3_PORT 与加密方式不匹配", result["message"])

    def test_poll_mailbox_supports_pop3_recent_scan(self) -> None:
        import app.services.mail as mail_module

        original_protocol = settings.mail_inbox_protocol
        original_host = settings.pop3_host
        original_port = settings.pop3_port
        original_user = settings.pop3_user
        original_password = settings.pop3_password
        original_ssl = settings.pop3_use_ssl
        original_tls = settings.pop3_use_tls
        original_max_scan = settings.mail_inbox_max_scan
        original_factory = mail_module._make_zmail_mail_server
        settings.mail_inbox_protocol = "pop3"
        settings.pop3_host = "pop3.example.com"
        settings.pop3_port = 110
        settings.pop3_user = "user"
        settings.pop3_password = "pass"
        settings.pop3_use_ssl = False
        settings.pop3_use_tls = False
        settings.mail_inbox_max_scan = 2

        class FakePOPServer:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def list(self):
                return b"+OK", [b"1 100", b"2 100", b"3 100"], 0

            def get_mail(self, message_number: int):
                message = EmailMessage()
                message["Message-ID"] = f"<pop3-{message_number}@example.com>"
                message["Subject"] = "任务#1 进行中"
                message["From"] = "member@example.com"
                message["Date"] = "Wed, 22 Apr 2026 10:00:00 +0800"
                message.set_content("任务#1 进行中")
                return message.as_bytes().splitlines()

            @property
            def server(self):
                return self

        class FakeMailServer:
            pop_server = FakePOPServer()

        mail_module._make_zmail_mail_server = lambda u, p: FakeMailServer()
        try:
            with SessionLocal() as db:
                db.add(User(username="member", password_hash=hash_password("x"), role="member", name="成员", email="member@example.com", ip_address="10.0.0.2", is_active=True))
                task = Task(title="测试任务", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=1)
                db.add(task)
                db.flush()
                db.add(TaskMember(task_id=task.id, user_id=1, member_role="owner"))
                db.add(Template(name="进行中模板", template_kind="MAIL_REPLY", notify_type="task_in_progress", priority=100, version=1, enabled=True, is_default=True, subject_rule="进行中", body_rule="进行中", content=""))
                initialize_mail_scan_baseline(db)
                db.query(MailScanState).filter(MailScanState.id == 1).update({"baseline_started_at": datetime(2026, 4, 21, 0, 0, 0), "last_scan_at": datetime(2026, 4, 21, 0, 0, 0)})
                db.commit()
                result = poll_mailbox(db)
                self.assertEqual(result["status"], "success")
                self.assertEqual(result["count"], 2)
                self.assertIn("POP3", result["message"])
        finally:
            mail_module._make_zmail_mail_server = original_factory
            settings.mail_inbox_protocol = original_protocol
            settings.pop3_host = original_host
            settings.pop3_port = original_port
            settings.pop3_user = original_user
            settings.pop3_password = original_password
            settings.pop3_use_ssl = original_ssl
            settings.pop3_use_tls = original_tls
            settings.mail_inbox_max_scan = original_max_scan

    def test_poll_mailbox_pop3_decodes_base64_reply_body(self) -> None:
        import app.services.mail as mail_module

        original_protocol = settings.mail_inbox_protocol
        original_host = settings.pop3_host
        original_port = settings.pop3_port
        original_user = settings.pop3_user
        original_password = settings.pop3_password
        original_ssl = settings.pop3_use_ssl
        original_tls = settings.pop3_use_tls
        original_max_scan = settings.mail_inbox_max_scan
        original_factory = mail_module._make_zmail_mail_server
        settings.mail_inbox_protocol = "pop3"
        settings.pop3_host = "pop3.intranet.local"
        settings.pop3_port = 110
        settings.pop3_user = "workflow"
        settings.pop3_password = "pass"
        settings.pop3_use_ssl = False
        settings.pop3_use_tls = False
        settings.mail_inbox_max_scan = 20

        class FakePOPServer:
            def __init__(self) -> None:
                payload = base64.b64encode("\u8fdb\u884c\u4e2d\r\n\r\n\u5185\u7f51\u90ae\u7bb1\u56de\u590d".encode("utf-8"))
                self.raw_message = (
                    b"Message-ID: <pop3-base64-1@example.local>\r\n"
                    b"Subject: =?utf-8?b?5Zue5aSNOuOAkOS7u+WKoemAmuefpSMx44CR?=\r\n"
                    b"From: member@example.local\r\n"
                    b"Date: Wed, 22 Apr 2026 10:00:00 +0800\r\n"
                    b'MIME-Version: 1.0\r\n'
                    b'Content-Type: text/plain; charset="utf-8"\r\n'
                    b"Content-Transfer-Encoding: base64\r\n"
                    b"\r\n"
                    + payload
                    + b"\r\n"
                )

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def list(self):
                return b"+OK", [b"1 300"], 0

            def top(self, message_number: int, line_count: int):
                if line_count == 0:
                    header = self.raw_message.split(b"\r\n\r\n", 1)[0]
                    return b"+OK", header.splitlines(), 0
                return b"+OK", self.raw_message.splitlines(), 0

            @property
            def server(self):
                return self

        class FakeMailServer:
            pop_server = FakePOPServer()

        mail_module._make_zmail_mail_server = lambda u, p: FakeMailServer()
        try:
            with SessionLocal() as db:
                member = User(username="member", password_hash=hash_password("x"), role="member", name="\u6210\u5458", email="member@example.local", ip_address="10.0.0.2", is_active=True)
                db.add(member)
                db.flush()
                task = Task(title="\u5185\u7f51POP3\u6d4b\u8bd5", content="\u5185\u5bb9", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=member.id)
                db.add(task)
                db.flush()
                db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="owner"))
                db.add(Template(name="\u8fdb\u884c\u4e2d\u6a21\u677f", template_kind="MAIL_REPLY", notify_type="task_in_progress", priority=100, version=1, enabled=True, is_default=True, subject_rule="\u8fdb\u884c\u4e2d", body_rule="\u8fdb\u884c\u4e2d", content=""))
                initialize_mail_scan_baseline(db)
                db.query(MailScanState).filter(MailScanState.id == 1).update({"baseline_started_at": datetime(2026, 4, 21, 0, 0, 0), "last_scan_at": datetime(2026, 4, 21, 0, 0, 0)})
                db.commit()

                result = poll_mailbox(db)
                db.refresh(task)

                self.assertEqual(result["status"], "success")
                self.assertEqual(result["count"], 1)
                self.assertEqual(task.main_status, "in_progress")
                event = db.query(MailEvent).first()
                self.assertIsNotNone(event)
                self.assertIn("\u8fdb\u884c\u4e2d", event.original_body)
        finally:
            mail_module._make_zmail_mail_server = original_factory
            settings.mail_inbox_protocol = original_protocol
            settings.pop3_host = original_host
            settings.pop3_port = original_port
            settings.pop3_user = original_user
            settings.pop3_password = original_password
            settings.pop3_use_ssl = original_ssl
            settings.pop3_use_tls = original_tls
            settings.mail_inbox_max_scan = original_max_scan

    def test_poll_mailbox_returns_busy_when_another_poll_is_running(self) -> None:
        import app.services.mail as mail_module

        acquired = mail_module._MAIL_POLL_EXECUTION_LOCK.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            with SessionLocal() as db:
                result = poll_mailbox(db)
        finally:
            if acquired:
                mail_module._MAIL_POLL_EXECUTION_LOCK.release()

        self.assertEqual(result["status"], "busy")
        self.assertIn("稍后重试", result["message"])
        self.assertEqual(result["count"], 0)

    def test_extract_text_body_accepts_unknown_8bit_charset(self) -> None:
        message = EmailMessage()
        message.set_payload("这是一封测试邮件".encode("utf-8"))
        message.set_type("text/plain")
        message.set_param("charset", "unknown-8bit")

        body = _extract_text_body(message)

        self.assertIn("测试邮件", body)

    def test_extract_text_body_falls_back_to_html_and_decodes_entities(self) -> None:
        message = EmailMessage()
        message.set_type("text/html")
        message.set_payload("<div>第一行&nbsp;内容</div><div>第二行<br>继续</div>".encode("utf-8"))
        message.set_param("charset", "utf-8")

        body = _extract_text_body(message)

        self.assertIn("第一行 内容", body)
        self.assertIn("第二行", body)
        self.assertIn("继续", body)

    def test_plain_text_to_html_preserves_line_breaks_and_spaces(self) -> None:
        html_content = _plain_text_to_html("第一行  两个空格\n第二行")

        self.assertIn("第一行&nbsp;&nbsp;两个空格<br>第二行", html_content)

    def test_find_task_id_prefers_explicit_id_marker(self) -> None:
        subject = "回复：任务通知提醒#2：任务1 进行中+任务1开始执行"
        body = "任务编号：2 任务名称：任务1 请尽快处理。"
        self.assertEqual(_find_task_id(subject, body), 2)

    def test_find_task_id_supports_fixed_task_notification_subject(self) -> None:
        self.assertEqual(_find_task_id("回复：【任务通知#18】任务1测试", "已完成"), 18)
        self.assertEqual(_find_task_id("回复：【任务通知#18】（更新）任务1测试", "已完成"), 18)
        self.assertEqual(_find_task_id("Re: 【任务通知＃19】任务2测试", "进行中"), 19)

    def test_in_progress_reply_does_not_mark_subtasks_done(self) -> None:
        with SessionLocal() as db:
            member = User(
                username="member",
                password_hash=hash_password("x"),
                role="member",
                name="成员",
                email="member@example.com",
                ip_address="10.0.0.2",
                is_active=True,
            )
            db.add(member)
            db.flush()
            task = Task(
                title="子任务进行中回执",
                content="内容",
                priority="medium",
                remark="",
                start_at=datetime(2026, 4, 20, 9, 0, 0),
                end_at=datetime(2026, 4, 25, 18, 0, 0),
                planned_minutes=60,
                actual_minutes=0,
                main_status="not_started",
                delay_days=0,
                state_locked=False,
                created_by=member.id,
            )
            db.add(task)
            db.flush()
            db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="owner"))
            subtask = TaskSubtask(
                task_id=task.id,
                title="子任务 A",
                content="",
                assignee_id=member.id,
                sort_order=0,
                status="pending",
            )
            db.add(subtask)
            mail_event = MailEvent(
                message_id="<progress-subtask@example.com>",
                from_addr="member@example.com",
                subject=f"回复：【任务通知#{task.id}】子任务进行中回执",
                body_digest="进行中",
                original_body="进行中",
                process_status="MATCHED",
            )
            db.add(mail_event)
            db.flush()

            _apply_task_status_from_mail(
                db,
                mail_event,
                "task_in_progress",
                member,
                mail_event.subject,
                mail_event.original_body,
            )
            db.flush()
            db.refresh(task)
            db.refresh(subtask)

        self.assertEqual(task.main_status, "in_progress")
        self.assertEqual(subtask.status, "in_progress")

    def test_one_done_reply_keeps_multi_member_task_in_progress(self) -> None:
        with SessionLocal() as db:
            first = User(username="first", password_hash=hash_password("x"), role="member", name="成员一", email="first@example.com", ip_address="10.0.0.2", is_active=True)
            second = User(username="second", password_hash=hash_password("x"), role="member", name="成员二", email="second@example.com", ip_address="10.0.0.3", is_active=True)
            db.add_all([first, second])
            db.flush()
            task = Task(title="多人完成聚合", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=first.id)
            db.add(task)
            db.flush()
            db.add_all([
                TaskMember(task_id=task.id, user_id=first.id, member_role="owner"),
                TaskMember(task_id=task.id, user_id=second.id, member_role="participant"),
            ])
            first_subtask = TaskSubtask(task_id=task.id, title="成员一子任务", content="", assignee_id=first.id, sort_order=0, status="pending")
            second_subtask = TaskSubtask(task_id=task.id, title="成员二子任务", content="", assignee_id=second.id, sort_order=1, status="pending")
            db.add_all([first_subtask, second_subtask])
            mail_event = MailEvent(message_id="<first-done@example.com>", from_addr=first.email, subject=f"回复：【任务通知#{task.id}】多人完成聚合", body_digest="已完成", original_body="已完成", process_status="MATCHED")
            db.add(mail_event)
            db.flush()

            _apply_task_status_from_mail(db, mail_event, "task_done", first, mail_event.subject, mail_event.original_body)
            db.flush()
            db.refresh(task)
            db.refresh(first_subtask)
            db.refresh(second_subtask)

        self.assertEqual(task.main_status, "in_progress")
        self.assertEqual(first_subtask.status, "done")
        self.assertEqual(second_subtask.status, "pending")

    def test_all_members_done_replies_complete_task_without_subtasks(self) -> None:
        with SessionLocal() as db:
            first = User(username="first", password_hash=hash_password("x"), role="member", name="成员一", email="first@example.com", ip_address="10.0.0.2", is_active=True)
            second = User(username="second", password_hash=hash_password("x"), role="member", name="成员二", email="second@example.com", ip_address="10.0.0.3", is_active=True)
            db.add_all([first, second])
            db.flush()
            task = Task(title="无子任务全部完成", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=first.id)
            db.add(task)
            db.flush()
            db.add_all([
                TaskMember(task_id=task.id, user_id=first.id, member_role="owner"),
                TaskMember(task_id=task.id, user_id=second.id, member_role="participant"),
            ])
            first_event = MailEvent(message_id="<first-done@example.com>", from_addr=first.email, subject=f"回复：【任务通知#{task.id}】无子任务全部完成", body_digest="已完成", original_body="已完成", process_status="MATCHED")
            db.add(first_event)
            db.flush()
            _apply_task_status_from_mail(db, first_event, "task_done", first, first_event.subject, first_event.original_body)
            db.flush()
            db.refresh(task)
            self.assertEqual(task.main_status, "in_progress")

            second_event = MailEvent(message_id="<second-done@example.com>", from_addr=second.email, subject=f"回复：【任务通知#{task.id}】无子任务全部完成", body_digest="已完成", original_body="已完成", process_status="MATCHED")
            db.add(second_event)
            db.flush()
            _apply_task_status_from_mail(db, second_event, "task_done", second, second_event.subject, second_event.original_body)
            db.flush()
            db.refresh(task)

        self.assertEqual(task.main_status, "done")

    def test_poll_mailbox_limits_recent_unseen_count(self) -> None:
        import app.services.mail as mail_module

        original_max_scan = settings.imap_max_unseen_scan
        original_inbox_max_scan = settings.mail_inbox_max_scan
        original_host = settings.imap_host
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_inbox_protocol = settings.mail_inbox_protocol
        settings.mail_inbox_protocol = "imap"
        settings.imap_max_unseen_scan = 2
        settings.mail_inbox_max_scan = 2
        settings.imap_host = "imap.example.com"
        settings.imap_user = "user"
        settings.imap_password = "pass"
        settings.imap_use_ssl = True
        settings.imap_use_tls = False

        class DummyImap:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, user, password):
                return "OK", []

            def select(self, mailbox):
                return "OK", []

            def search(self, *args):
                return "OK", [b"1 2 3 4 5"]

            def fetch(self, imap_id, _):
                message = EmailMessage()
                message["Message-ID"] = f"<msg-{imap_id.decode()}@example.com>"
                message["Subject"] = "任务#1 进行中"
                message["From"] = "member@example.com"
                message["Date"] = "Wed, 22 Apr 2026 10:00:00 +0800"
                message.set_content("任务#1 进行中")
                return "OK", [(None, message.as_bytes())]

        original_imap = mail_module.imaplib.IMAP4_SSL
        mail_module.imaplib.IMAP4_SSL = lambda host, port: DummyImap()

        try:
            with SessionLocal() as db:
                db.add(User(username="member", password_hash=hash_password("x"), role="member", name="成员", email="member@example.com", ip_address="10.0.0.2", is_active=True))
                task = Task(title="测试任务", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=1)
                db.add(task)
                db.flush()
                db.add(TaskMember(task_id=task.id, user_id=1, member_role="owner"))
                db.add(Template(name="进行中模板", template_kind="MAIL_REPLY", notify_type="task_in_progress", priority=100, version=1, enabled=True, is_default=True, subject_rule="进行中", body_rule="进行中", content=""))
                baseline_result = initialize_mail_scan_baseline(db)
                self.assertEqual(baseline_result["status"], "success")
                db.query(MailScanState).filter(MailScanState.id == 1).update({"baseline_started_at": datetime(2026, 4, 21, 0, 0, 0), "last_scan_at": datetime(2026, 4, 21, 0, 0, 0)})
                db.commit()
                result = poll_mailbox(db)
                self.assertEqual(result["status"], "success")
                self.assertEqual(result["count"], 2)
        finally:
            mail_module.imaplib.IMAP4_SSL = original_imap
            settings.imap_max_unseen_scan = original_max_scan
            settings.mail_inbox_max_scan = original_inbox_max_scan
            settings.mail_inbox_protocol = original_inbox_protocol
            settings.imap_host = original_host
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

    def test_first_poll_initializes_baseline_and_skips_history(self) -> None:
        with SessionLocal() as db:
            result = poll_mailbox(db)
        self.assertEqual(result["status"], "skipped" if "IMAP" in result["message"] else "initialized")

    def test_initialize_mail_scan_baseline_returns_success(self) -> None:
        with SessionLocal() as db:
            result = initialize_mail_scan_baseline(db)
        self.assertEqual(result["status"], "success")
        self.assertIn("2026-", result["message"])

    def test_poll_mailbox_updates_task_status_from_reply(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.imap_host
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_inbox_protocol = settings.mail_inbox_protocol
        settings.mail_inbox_protocol = "imap"
        settings.imap_host = "imap.example.com"
        settings.imap_user = "user"
        settings.imap_password = "pass"
        settings.imap_use_ssl = True
        settings.imap_use_tls = False

        class DummyImap:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, user, password):
                return "OK", []

            def select(self, mailbox):
                return "OK", []

            def search(self, *args):
                return "OK", [b"7"]

            def fetch(self, imap_id, _):
                message = EmailMessage()
                message["Message-ID"] = "<done-1@example.com>"
                message["Subject"] = "任务#1 已完成"
                message["From"] = "member@example.com"
                message["Date"] = "Wed, 23 Apr 2026 10:00:00 +0800"
                message.set_content("任务#1 已完成 备注")
                return "OK", [(None, message.as_bytes())]

        original_imap = mail_module.imaplib.IMAP4_SSL
        mail_module.imaplib.IMAP4_SSL = lambda host, port: DummyImap()
        try:
            with SessionLocal() as db:
                member = User(username="member", password_hash=hash_password("x"), role="member", name="成员", email="member@example.com", ip_address="10.0.0.2", is_active=True)
                db.add(member)
                db.flush()
                task = Task(title="测试任务", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=member.id)
                db.add(task)
                db.flush()
                db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="owner"))
                db.add(Template(name="完成模板", template_kind="MAIL_REPLY", notify_type="task_done", priority=100, version=1, enabled=True, is_default=True, subject_rule="已完成", body_rule="已完成", content=""))
                initialize_mail_scan_baseline(db)
                db.query(MailScanState).filter(MailScanState.id == 1).update({"baseline_started_at": datetime(2026, 4, 21, 0, 0, 0), "last_scan_at": datetime(2026, 4, 21, 0, 0, 0)})
                db.commit()
                result = poll_mailbox(db)
                db.refresh(task)
                self.assertEqual(result["status"], "success")
                self.assertEqual(task.main_status, "done")
                action = db.query(MailAction).first()
                self.assertIsNotNone(action)
                self.assertEqual(action.action_status, "APPLIED")
        finally:
            mail_module.imaplib.IMAP4_SSL = original_imap
            settings.mail_inbox_protocol = original_inbox_protocol
            settings.imap_host = original_host
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

    def test_poll_mailbox_creates_delay_request_from_reply(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.imap_host
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_inbox_protocol = settings.mail_inbox_protocol
        settings.mail_inbox_protocol = "imap"
        settings.imap_host = "imap.example.com"
        settings.imap_user = "user"
        settings.imap_password = "pass"
        settings.imap_use_ssl = True
        settings.imap_use_tls = False

        class DummyImap:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, user, password):
                return "OK", []

            def select(self, mailbox):
                return "OK", []

            def search(self, *args):
                return "OK", [b"9"]

            def fetch(self, imap_id, _):
                message = EmailMessage()
                message["Message-ID"] = "<delay-1@example.com>"
                message["Subject"] = "任务#1 延期"
                message["From"] = "member@example.com"
                message["Date"] = "Wed, 23 Apr 2026 11:00:00 +0800"
                message.set_content("任务#1 延期 2026-04-30 因为依赖未完成")
                return "OK", [(None, message.as_bytes())]

        original_imap = mail_module.imaplib.IMAP4_SSL
        mail_module.imaplib.IMAP4_SSL = lambda host, port: DummyImap()
        try:
            with SessionLocal() as db:
                admin = User(username="admin", password_hash=hash_password("x"), role="admin", name="管理员", email="admin@example.com", ip_address="10.0.0.1", is_active=True)
                member = User(username="member", password_hash=hash_password("x"), role="member", name="成员", email="member@example.com", ip_address="10.0.0.2", is_active=True)
                db.add_all([admin, member])
                db.flush()
                task = Task(title="测试任务", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="in_progress", delay_days=0, state_locked=False, created_by=member.id)
                db.add(task)
                db.flush()
                db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="owner"))
                db.add(Template(name="延期模板", template_kind="MAIL_REPLY", notify_type="delay_request", priority=100, version=1, enabled=True, is_default=True, subject_rule="延期", body_rule="延期", content=""))
                initialize_mail_scan_baseline(db)
                db.query(MailScanState).filter(MailScanState.id == 1).update({"baseline_started_at": datetime(2026, 4, 21, 0, 0, 0), "last_scan_at": datetime(2026, 4, 21, 0, 0, 0)})
                db.commit()
                result = poll_mailbox(db)
                self.assertEqual(result["status"], "success")
                # 当前业务层将延期申请类邮件标记为跳过（审批链路停用），不再写入 DelayRequest。
                self.assertEqual(db.query(DelayRequest).count(), 0)
                delay_action = db.query(MailAction).filter(MailAction.action_type == "delay_request").first()
                self.assertIsNotNone(delay_action)
                self.assertEqual(delay_action.action_status, "SKIPPED")
        finally:
            mail_module.imaplib.IMAP4_SSL = original_imap
            settings.mail_inbox_protocol = original_inbox_protocol
            settings.imap_host = original_host
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

    def test_poll_mailbox_does_not_treat_system_notification_as_member_reply(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.imap_host
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_inbox_protocol = settings.mail_inbox_protocol
        settings.mail_inbox_protocol = "imap"
        settings.imap_host = "imap.example.com"
        settings.imap_user = "user"
        settings.imap_password = "pass"
        settings.imap_use_ssl = True
        settings.imap_use_tls = False

        class DummyImap:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def login(self, user, password):
                return "OK", []

            def select(self, mailbox):
                return "OK", []

            def search(self, *args):
                return "OK", [b"11"]

            def fetch(self, imap_id, _):
                message = EmailMessage()
                message["Message-ID"] = "<system-task-created@example.com>"
                message["Subject"] = "回复：任务通知提醒#1：测试任务"
                message["From"] = "admin@example.com"
                message["Date"] = "Wed, 23 Apr 2026 11:30:00 +0800"
                message.set_content(
                    "您好，系统管理员\n"
                    "任务创建人：系统管理员\n"
                    "负责人：系统管理员\n"
                    "任务编号：1\n"
                    "任务名称：测试任务\n"
                    "开始时间：2026-04-20 09:00\n"
                    "结束时间：2026-04-25 18:00\n"
                    "主任务详情：内容\n"
                    "当前提醒重点：主任务整体进度跟进\n"
                    "子任务安排：\n"
                    "当前接收人暂无分配子任务\n\n"
                    "回复指引：\n"
                    "1. 回复“进行中 + 备注”可更新任务状态。\n"
                    "2. 回复“已完成 + 备注”可将任务标记为完成。\n"
                    "3. 如需延期，请回复“延期 + 新日期 + 原因”。\n"
                )
                return "OK", [(None, message.as_bytes())]

        original_imap = mail_module.imaplib.IMAP4_SSL
        mail_module.imaplib.IMAP4_SSL = lambda host, port: DummyImap()
        try:
            with SessionLocal() as db:
                admin = User(username="admin", password_hash=hash_password("x"), role="system_admin", name="系统管理员", email="admin@example.com", ip_address="10.0.0.1", is_active=True)
                db.add(admin)
                db.flush()
                task = Task(title="测试任务", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=admin.id)
                db.add(task)
                db.flush()
                db.add(TaskMember(task_id=task.id, user_id=admin.id, member_role="owner"))
                db.add(Template(name="完成模板", template_kind="MAIL_REPLY", notify_type="task_done", priority=120, version=1, enabled=True, is_default=True, subject_rule="已完成|完成", body_rule="已完成|完成", content=""))
                db.add(Template(name="延期模板", template_kind="MAIL_REPLY", notify_type="delay_request", priority=130, version=1, enabled=True, is_default=True, subject_rule="延期", body_rule="延期", content=""))
                notification = Notification(task_id=task.id, channel="email", notify_type="task_created", content_snapshot="任务创建通知", status="delivered")
                db.add(notification)
                db.flush()
                recipient = NotificationRecipient(notification_id=notification.id, user_id=admin.id, recipient_role="owner", delivery_status="delivered", read_status="unread", retry_count=0, content_snapshot="任务创建通知", last_error="")
                db.add(recipient)
                initialize_mail_scan_baseline(db)
                db.query(MailScanState).filter(MailScanState.id == 1).update({"baseline_started_at": datetime(2026, 4, 21, 0, 0, 0), "last_scan_at": datetime(2026, 4, 21, 0, 0, 0)})
                db.commit()

                result = poll_mailbox(db)

                db.refresh(task)
                db.refresh(recipient)
                self.assertEqual(result["status"], "success")
                self.assertEqual(task.main_status, "not_started")
                self.assertEqual(recipient.read_status, "unread")
                # 系统生成的通知经 strip_reply_guides 后通常无法命中回复模板，不产生业务 MailAction。
                self.assertEqual(db.query(MailAction).count(), 0)
                self.assertEqual(db.query(DelayRequest).count(), 0)
        finally:
            mail_module.imaplib.IMAP4_SSL = original_imap
            settings.mail_inbox_protocol = original_inbox_protocol
            settings.imap_host = original_host
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

    def test_mark_notification_recipient_replied_updates_latest_email_notification(self) -> None:
        with SessionLocal() as db:
            member = User(username="member", password_hash=hash_password("x"), role="member", name="成员", email="member@example.com", ip_address="10.0.0.2", is_active=True)
            db.add(member)
            db.flush()
            task = Task(title="测试任务", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="not_started", delay_days=0, state_locked=False, created_by=member.id)
            db.add(task)
            db.flush()

            earlier_notification = Notification(task_id=task.id, channel="email", notify_type="task_created", content_snapshot="创建通知", status="delivered")
            latest_notification = Notification(task_id=task.id, channel="email", notify_type="task_updated", content_snapshot="更新通知", status="delivered")
            db.add_all([earlier_notification, latest_notification])
            db.flush()
            db.add_all(
                [
                    NotificationRecipient(notification_id=earlier_notification.id, user_id=member.id, recipient_role="owner", delivery_status="delivered", read_status="unread", retry_count=0, content_snapshot="创建通知", last_error=""),
                    NotificationRecipient(notification_id=latest_notification.id, user_id=member.id, recipient_role="owner", delivery_status="delivered", read_status="unread", retry_count=0, content_snapshot="更新通知", last_error=""),
                ]
            )
            mail_event = MailEvent(
                message_id="<reply-1@example.com>",
                from_addr="member@example.com",
                subject="任务#1 已完成",
                body_digest="任务#1 已完成",
                original_body="任务#1 已完成",
                process_status="MATCHED",
            )
            db.add(mail_event)
            db.commit()
            db.refresh(mail_event)

            recipient_id = _mark_notification_recipient_replied(
                db,
                task.id,
                member.id,
                mail_event,
                ("task_created", "task_updated", "manual_remind", "due_remind"),
            )
            db.commit()

            self.assertIsNotNone(recipient_id)
            recipients = db.query(NotificationRecipient).order_by(NotificationRecipient.id.asc()).all()
            self.assertEqual(recipients[0].read_status, "unread")
            self.assertEqual(recipients[1].read_status, "read")
            self.assertEqual(recipient_id, recipients[1].id)

    def test_done_reply_without_task_id_fails_without_explicit_task_id(self) -> None:
        with SessionLocal() as db:
            member = User(username="member", password_hash=hash_password("x"), role="member", name="成员", email="member@example.com", ip_address="10.0.0.2", is_active=True)
            db.add(member)
            db.flush()
            task = Task(title="到期任务", content="内容", priority="medium", remark="", start_at=datetime(2026, 4, 20, 9, 0, 0), end_at=datetime(2026, 4, 25, 18, 0, 0), planned_minutes=60, actual_minutes=0, main_status="in_progress", delay_days=0, state_locked=False, created_by=member.id)
            db.add(task)
            db.flush()
            db.add(TaskMember(task_id=task.id, user_id=member.id, member_role="owner"))
            template = Template(name="完成模板", template_kind="MAIL_REPLY", notify_type="task_done", priority=120, version=1, enabled=True, is_default=True, subject_rule="已完成|完成", body_rule="已完成|完成", content="")
            db.add(template)
            db.flush()
            notification = Notification(task_id=task.id, channel="email", notify_type="due_remind", content_snapshot="到期提醒", status="delivered")
            db.add(notification)
            db.flush()
            recipient = NotificationRecipient(notification_id=notification.id, user_id=member.id, recipient_role="owner", delivery_status="delivered", read_status="unread", retry_count=0, content_snapshot="到期提醒", last_error="")
            db.add(recipient)
            state = MailScanState(id=1, baseline_started_at=None, last_scan_at=None)
            db.add(state)
            db.commit()

            message = EmailMessage()
            message["Message-ID"] = "<done-without-task-id@example.com>"
            message["Subject"] = "回复：任务到期提醒"
            message["From"] = "member@example.com"
            message["Date"] = "Wed, 24 Jun 2026 10:00:00 +0800"
            message.set_content("已完成")

            saved = _build_mail_event_from_message(
                db,
                state,
                message.as_bytes(),
                "imap-INBOX-22",
                inbox_protocol="imap",
                inbox_folder="INBOX",
                server_message_ref="22",
                templates=[(template, ("已完成", "完成"), ("已完成", "完成"))],
                known_message_id="<done-without-task-id@example.com>",
                skip_existing_check=True,
            )
            db.commit()
            db.refresh(task)
            db.refresh(recipient)
            action = db.query(MailAction).one()
            event = db.query(MailEvent).one()

        self.assertTrue(saved)
        self.assertEqual(task.main_status, "in_progress")
        self.assertEqual(recipient.read_status, "unread")
        self.assertEqual(event.process_status, "FAILED")
        self.assertEqual(action.action_status, "FAILED")
        self.assertIn("未识别到任务ID", action.action_result_json)

    def test_build_mail_event_records_inbox_source_metadata(self) -> None:
        with SessionLocal() as db:
            state = MailScanState(id=1, baseline_started_at=None, last_scan_at=None)
            db.add(state)
            db.flush()

            raw_message = (
                b"Message-ID: <mail-1@example.com>\r\n"
                b"From: member@test.local\r\n"
                b"Subject: task update\r\n"
                b"Date: Tue, 23 Jun 2026 10:00:00 +0800\r\n"
                b"\r\n"
                b"in progress"
            )
            saved = _build_mail_event_from_message(
                db,
                state,
                raw_message,
                "imap-INBOX-1",
                inbox_protocol="imap",
                inbox_folder="INBOX",
                server_message_ref="88",
                templates=[],
                known_message_id="<mail-1@example.com>",
                skip_existing_check=True,
            )
            db.commit()
            event = db.query(MailEvent).filter(MailEvent.message_id == "<mail-1@example.com>").one()

        self.assertTrue(saved)
        self.assertEqual(event.inbox_protocol, "imap")
        self.assertEqual(event.inbox_folder, "INBOX")
        self.assertEqual(event.server_message_ref, "88")

    def test_delete_task_related_mail_from_inbox_removes_all_applied_task_reply_mails(self) -> None:
        with SessionLocal() as db:
            creator = User(
                username="creator",
                password_hash=hash_password("pass"),
                role="system_admin",
                name="Creator",
                email="creator@test.local",
                ip_address="10.0.0.9",
                is_active=True,
            )
            db.add(creator)
            db.flush()
            task = Task(
                title="任务1测试",
                content="content",
                priority="medium",
                remark="",
                start_at=datetime(2026, 6, 23, 9, 0, 0),
                end_at=datetime(2026, 6, 24, 18, 0, 0),
                created_by=creator.id,
            )
            db.add(task)
            db.flush()

            first = MailEvent(
                message_id="<progress@example.com>",
                from_addr="member@test.local",
                subject="任务 1测试 进行中",
                body_digest="进行中",
                original_body="进行中",
                inbox_protocol="imap",
                inbox_folder="INBOX",
                server_message_ref="101",
                process_status="APPLIED",
            )
            second = MailEvent(
                message_id="<done@example.com>",
                from_addr="member@test.local",
                subject="任务 1测试 已完成",
                body_digest="已完成",
                original_body="已完成",
                inbox_protocol="imap",
                inbox_folder="INBOX",
                server_message_ref="102",
                process_status="APPLIED",
            )
            original_notification = MailEvent(
                message_id="<original-notification@example.com>",
                from_addr="noreply@test.local",
                subject=f"\u3010\u4efb\u52a1\u901a\u77e5#{task.id}\u3011notification",
                body_digest="notification body",
                original_body="notification body",
                inbox_protocol="imap",
                inbox_folder="INBOX",
                server_message_ref="103",
                process_status="UNMATCHED",
            )
            db.add_all([first, second, original_notification])
            db.flush()
            db.add_all(
                [
                    MailAction(
                        mail_event_id=first.id,
                        action_type="task_in_progress",
                        target_task_id=task.id,
                        action_status="APPLIED",
                        action_result_json="{}",
                    ),
                    MailAction(
                        mail_event_id=second.id,
                        action_type="task_done",
                        target_task_id=task.id,
                        action_status="APPLIED",
                        action_result_json="{}",
                    ),
                ]
            )
            db.commit()

            with patch("app.services.mail._delete_imap_message") as mocked_delete:
                result = delete_task_related_mail_from_inbox(db, task.id)
                db.commit()

        self.assertEqual(result["matched_count"], 3)
        self.assertEqual(result["deleted_count"], 3)
        self.assertEqual(result["deleted_record_count"], 3)
        self.assertEqual(result["deleted_action_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(mocked_delete.call_count, 3)
        self.assertEqual(mocked_delete.call_args_list[0].args, ("INBOX", "101"))
        self.assertEqual(mocked_delete.call_args_list[1].args, ("INBOX", "102"))
        self.assertEqual(mocked_delete.call_args_list[2].args, ("INBOX", "103"))
        with SessionLocal() as db:
            self.assertEqual(db.query(MailEvent).count(), 0)
            self.assertEqual(db.query(MailAction).count(), 0)

    def test_cleanup_applied_task_reply_mails_deletes_only_same_recipient_original(self) -> None:
        original_from = settings.smtp_from_address
        settings.smtp_from_address = "noreply@test.local"
        try:
            with SessionLocal() as db:
                creator = User(
                    username="creator",
                    password_hash=hash_password("pass"),
                    role="system_admin",
                    name="Creator",
                    email="creator@test.local",
                    ip_address="10.0.0.9",
                    is_active=True,
                )
                db.add(creator)
                db.flush()
                task = Task(
                    title="任务18测试",
                    content="content",
                    priority="medium",
                    remark="",
                    start_at=datetime(2026, 6, 23, 9, 0, 0),
                    end_at=datetime(2026, 6, 24, 18, 0, 0),
                    created_by=creator.id,
                )
                db.add(task)
                db.flush()
                original_same_recipient = MailEvent(
                    message_id="<original-member@example.com>",
                    from_addr="任务管理助手 <noreply@test.local>",
                    to_addr="member@test.local",
                    subject=f"【任务通知#{task.id}】任务18测试",
                    body_digest="任务编号",
                    original_body="任务编号",
                    inbox_protocol="imap",
                    inbox_folder="INBOX",
                    server_message_ref="201",
                    process_status="UNMATCHED",
                )
                original_other_recipient = MailEvent(
                    message_id="<original-other@example.com>",
                    from_addr="任务管理助手 <noreply@test.local>",
                    to_addr="other@test.local",
                    subject=f"【任务通知#{task.id}】任务18测试",
                    body_digest="任务编号",
                    original_body="任务编号",
                    inbox_protocol="imap",
                    inbox_folder="INBOX",
                    server_message_ref="202",
                    process_status="UNMATCHED",
                )
                reply = MailEvent(
                    message_id="<reply-member@example.com>",
                    from_addr="member@test.local",
                    to_addr="noreply@test.local",
                    subject=f"回复：【任务通知#{task.id}】任务18测试",
                    body_digest="已完成",
                    original_body="已完成",
                    inbox_protocol="imap",
                    inbox_folder="INBOX",
                    server_message_ref="203",
                    process_status="APPLIED",
                )
                db.add_all([original_same_recipient, original_other_recipient, reply])
                db.flush()
                db.add(
                    MailAction(
                        mail_event_id=reply.id,
                        action_type="task_done",
                        target_task_id=task.id,
                        action_status="APPLIED",
                        action_result_json="{}",
                    )
                )
                db.commit()

                with patch("app.services.mail._delete_imap_message") as mocked_delete:
                    result = cleanup_applied_task_reply_mails(db)
                    db.commit()

                db.refresh(original_same_recipient)
                db.refresh(original_other_recipient)
                db.refresh(reply)

            self.assertEqual(result["deleted_count"], 2)
            self.assertEqual(mocked_delete.call_count, 2)
            self.assertEqual(mocked_delete.call_args_list[0].args, ("INBOX", "201"))
            self.assertEqual(mocked_delete.call_args_list[1].args, ("INBOX", "203"))
            self.assertEqual(original_same_recipient.server_message_ref, "")
            self.assertEqual(reply.server_message_ref, "")
            self.assertEqual(original_other_recipient.server_message_ref, "202")
        finally:
            settings.smtp_from_address = original_from


if __name__ == "__main__":
    unittest.main()
