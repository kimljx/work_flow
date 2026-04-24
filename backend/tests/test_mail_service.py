from __future__ import annotations

import socket
import ssl
import unittest
from datetime import datetime
from email.message import EmailMessage

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import DelayRequest, MailAction, MailScanState, Notification, Task, TaskMember, Template, User
from app.security import hash_password
from app.services.mail import (
    _extract_text_body,
    _find_task_id,
    diagnose_imap_settings,
    diagnose_mail_settings,
    initialize_mail_scan_baseline,
    poll_mailbox,
    send_mail_notification,
)


class MailServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

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
        from app.services.mail import _open_smtp_connection
        import smtplib

        original_host = settings.smtp_host
        original_port = settings.smtp_port
        original_ssl = settings.smtp_use_ssl
        settings.smtp_host = "smtp.example.com"
        settings.smtp_port = 465
        settings.smtp_use_ssl = False

        captured = {}
        original_smtp_ssl = smtplib.SMTP_SSL

        class DummySMTPSSL:
            def __init__(self, host, port, timeout):
                captured["host"] = host
                captured["port"] = port
                captured["timeout"] = timeout

        smtplib.SMTP_SSL = DummySMTPSSL
        try:
            _open_smtp_connection()
        finally:
            smtplib.SMTP_SSL = original_smtp_ssl
            settings.smtp_host = original_host
            settings.smtp_port = original_port
            settings.smtp_use_ssl = original_ssl

        self.assertEqual(captured["port"], 465)

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
        settings.imap_host = ""
        settings.imap_user = ""
        try:
            result = diagnose_imap_settings()
        finally:
            settings.imap_host = original_host
            settings.imap_user = original_user

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
            settings.imap_host = original_host
            settings.imap_port = original_port
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls

        self.assertEqual(result["status"], "success")

    def test_diagnose_imap_returns_actionable_message_for_ssl_wrong_version(self) -> None:
        import app.services.mail as mail_module

        original_host = settings.imap_host
        original_port = settings.imap_port
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
        original_open = mail_module._open_imap_connection
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
        original_pop3 = mail_module.poplib.POP3
        settings.mail_inbox_protocol = "pop3"
        settings.pop3_host = "pop3.example.com"
        settings.pop3_port = 110
        settings.pop3_user = "user"
        settings.pop3_password = "pass"
        settings.pop3_use_ssl = False
        settings.pop3_use_tls = False

        class DummyPop3:
            def user(self, username):
                return b"+OK"

            def pass_(self, password):
                return b"+OK"

            def quit(self):
                return b"+OK"

        mail_module.poplib.POP3 = lambda host, port, timeout=None: DummyPop3()
        try:
            result = diagnose_imap_settings()
        finally:
            mail_module.poplib.POP3 = original_pop3
            settings.mail_inbox_protocol = original_protocol
            settings.pop3_host = original_host
            settings.pop3_port = original_port
            settings.pop3_user = original_user
            settings.pop3_password = original_password
            settings.pop3_use_ssl = original_ssl
            settings.pop3_use_tls = original_tls

        self.assertEqual(result["status"], "success")
        self.assertIn("POP3", result["message"])

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
        original_pop3 = mail_module.poplib.POP3
        settings.mail_inbox_protocol = "pop3"
        settings.pop3_host = "pop3.example.com"
        settings.pop3_port = 110
        settings.pop3_user = "user"
        settings.pop3_password = "pass"
        settings.pop3_use_ssl = False
        settings.pop3_use_tls = False
        settings.mail_inbox_max_scan = 2

        class DummyPop3:
            def user(self, username):
                return b"+OK"

            def pass_(self, password):
                return b"+OK"

            def list(self):
                return b"+OK", [b"1 100", b"2 100", b"3 100"], 0

            def retr(self, message_number):
                message = EmailMessage()
                message["Message-ID"] = f"<pop3-{message_number}@example.com>"
                message["Subject"] = "任务#1 进行中"
                message["From"] = "member@example.com"
                message["Date"] = "Wed, 22 Apr 2026 10:00:00 +0800"
                message.set_content("任务#1 进行中")
                return b"+OK", message.as_bytes().splitlines(), 0

            def quit(self):
                return b"+OK"

        mail_module.poplib.POP3 = lambda host, port, timeout=None: DummyPop3()
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
            mail_module.poplib.POP3 = original_pop3
            settings.mail_inbox_protocol = original_protocol
            settings.pop3_host = original_host
            settings.pop3_port = original_port
            settings.pop3_user = original_user
            settings.pop3_password = original_password
            settings.pop3_use_ssl = original_ssl
            settings.pop3_use_tls = original_tls
            settings.mail_inbox_max_scan = original_max_scan

    def test_extract_text_body_accepts_unknown_8bit_charset(self) -> None:
        message = EmailMessage()
        message.set_payload("这是一封测试邮件".encode("utf-8"))
        message.set_type("text/plain")
        message.set_param("charset", "unknown-8bit")

        body = _extract_text_body(message)

        self.assertIn("测试邮件", body)

    def test_find_task_id_prefers_explicit_id_marker(self) -> None:
        subject = "回复：任务通知提醒#2：任务1 进行中+任务1开始执行"
        body = "任务编号：2 任务名称：任务1 请尽快处理。"
        self.assertEqual(_find_task_id(subject, body), 2)

    def test_poll_mailbox_limits_recent_unseen_count(self) -> None:
        import app.services.mail as mail_module

        original_max_scan = settings.imap_max_unseen_scan
        original_inbox_max_scan = settings.mail_inbox_max_scan
        original_host = settings.imap_host
        original_user = settings.imap_user
        original_password = settings.imap_password
        original_ssl = settings.imap_use_ssl
        original_tls = settings.imap_use_tls
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
                self.assertEqual(db.query(DelayRequest).count(), 1)
                self.assertGreaterEqual(db.query(Notification).count(), 2)
        finally:
            mail_module.imaplib.IMAP4_SSL = original_imap
            settings.imap_host = original_host
            settings.imap_user = original_user
            settings.imap_password = original_password
            settings.imap_use_ssl = original_ssl
            settings.imap_use_tls = original_tls


if __name__ == "__main__":
    unittest.main()
