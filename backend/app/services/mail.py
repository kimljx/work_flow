from __future__ import annotations

"""邮件接入服务。

负责 SMTP 连通性检测、IMAP 收件、邮件正文解析、模板匹配以及
“邮件驱动任务状态 / 延期审批”的业务处理。
"""

import email
import hashlib
import imaplib
import json
import poplib
import re
import ssl
import smtplib
import socket
from datetime import datetime
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import parseaddr, parsedate_to_datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DelayRequest, MailAction, MailEvent, MailScanState, Task, TaskMember, TaskStatusEvent, TaskSubtask, Template, User
from app.services.delay import apply_delay_decision
from app.services.templates import sort_templates, template_matches
from app.timeutils import shanghai_now_naive, to_shanghai_naive


DATE_PATTERN = re.compile(r"(20\d{2})(?:-|/|年)(\d{1,2})(?:-|/|月)(\d{1,2})(?:日)?")
TASK_ID_PATTERN = re.compile(r"(?:任务\s*(?:ID|编号)\s*[#:：]?\s*|任务\s*#\s*)(\d+)", re.IGNORECASE)
DELAY_REQUEST_ID_PATTERN = re.compile(r"(?:延期申请\s*(?:ID|编号)\s*[#:：]?\s*|延期申请\s*#\s*)(\d+)", re.IGNORECASE)


def _provider_hint() -> str:
    """根据已知服务商给出更有针对性的配置提示。"""
    host = settings.smtp_host.lower().strip()
    if "qq.com" in host:
        if settings.smtp_port == 587 and not settings.smtp_use_tls:
            return "QQ 邮箱使用 587 端口时请开启 STARTTLS。"
        return "QQ 邮箱建议使用授权码作为 SMTP 密码。"
    return ""


def _inbox_protocol() -> str:
    """返回当前启用的收件协议。"""
    return "pop3" if settings.mail_inbox_protocol == "pop3" else "imap"


def _inbox_protocol_text() -> str:
    """返回当前收件协议的中文展示名称。"""
    return "POP3" if _inbox_protocol() == "pop3" else "IMAP"


def _generic_hint() -> str:
    """返回通用的 SMTP 排障建议。"""
    return (
        "请确认 SMTP_HOST 填写的是纯域名，不要包含 http:// 或 https:// 前缀；"
        "并检查 DNS 配置是否可解析该域名。"
    )


def _smtp_security_mode_text() -> str:
    """返回当前 SMTP 加密方式的中文说明。"""
    if settings.smtp_use_ssl or settings.smtp_port == 465:
        return "SSL 直连"
    if settings.smtp_use_tls:
        return "STARTTLS"
    return "明文连接"


def _smtp_security_recommendation() -> str:
    """根据常见端口返回更贴近用户操作的配置建议。"""
    if settings.smtp_port == 465:
        return "465 端口通常需要设置 SMTP_USE_SSL=true 且 SMTP_USE_TLS=false。"
    if settings.smtp_port == 587:
        return "587 端口通常需要设置 SMTP_USE_TLS=true 且 SMTP_USE_SSL=false。"
    if settings.smtp_port == 25:
        return "25 端口通常保持 SMTP_USE_SSL=false，是否开启 SMTP_USE_TLS 取决于服务商是否要求 STARTTLS。"
    return "请检查 SMTP 端口与 SMTP_USE_SSL、SMTP_USE_TLS 是否匹配，且不要同时开启两种加密方式。"


def _smtp_ssl_error_hint(exc: ssl.SSLError) -> str:
    """将底层 SSL 握手错误转换为更容易理解的中文提示。

    说明:
    - `_ssl.c:1007` 常见于 `WRONG_VERSION_NUMBER`，本质上多数是端口与加密方式不匹配；
    - 这里统一转成“当前配置 + 推荐配置”的形式，便于运维直接修改 `.env`。
    """
    message = str(exc).lower()
    if "wrong version number" in message:
        return (
            f"SMTP SSL/TLS 握手失败，当前使用的是“{_smtp_security_mode_text()}”，"
            f"这通常不是协议版本真的错误，而是端口与加密方式不匹配。{_smtp_security_recommendation()}"
        )
    if "ssl" in message or "tls" in message:
        return f"SMTP SSL/TLS 握手失败。{_smtp_security_recommendation()}"
    return f"SMTP 建立安全连接失败：{exc}"


def _imap_security_mode_text() -> str:
    """返回当前 IMAP 加密方式的中文说明。"""
    if settings.imap_use_ssl or settings.imap_port == 993:
        return "SSL 直连"
    if settings.imap_use_tls:
        return "STARTTLS"
    return "明文连接"


def _imap_security_recommendation() -> str:
    """根据常见 IMAP 端口返回推荐配置。"""
    if settings.imap_port == 993:
        return "993 端口通常需要设置 IMAP_USE_SSL=true 且 IMAP_USE_TLS=false。"
    if settings.imap_port == 143:
        return "143 端口通常需要设置 IMAP_USE_SSL=false，是否开启 IMAP_USE_TLS 取决于服务商是否要求 STARTTLS。"
    return "请检查 IMAP 端口与 IMAP_USE_SSL、IMAP_USE_TLS 是否匹配，且不要同时开启两种加密方式。"


def _imap_ssl_error_hint(exc: ssl.SSLError) -> str:
    """将 IMAP 底层 SSL/TLS 错误转换为中文提示。"""
    message = str(exc).lower()
    if "wrong version number" in message:
        return (
            f"IMAP SSL/TLS 握手失败，当前使用的是“{_imap_security_mode_text()}”，"
            f"这通常不是协议版本真的错误，而是端口与加密方式不匹配。{_imap_security_recommendation()}"
        )
    if "ssl" in message or "tls" in message:
        return f"IMAP SSL/TLS 握手失败。{_imap_security_recommendation()}"
    return f"IMAP 建立安全连接失败：{exc}"


def _pop3_security_mode_text() -> str:
    """返回当前 POP3 加密方式的中文说明。"""
    if settings.pop3_use_ssl or settings.pop3_port == 995:
        return "SSL 直连"
    if settings.pop3_use_tls:
        return "STLS"
    return "明文连接"


def _pop3_security_recommendation() -> str:
    """根据常见 POP3 端口返回推荐配置。"""
    if settings.pop3_port == 995:
        return "995 端口通常需要设置 POP3_USE_SSL=true 且 POP3_USE_TLS=false。"
    if settings.pop3_port == 110:
        return "110 端口通常需要设置 POP3_USE_SSL=false，是否开启 POP3_USE_TLS 取决于服务商是否要求 STLS。"
    return "请检查 POP3 端口与 POP3_USE_SSL、POP3_USE_TLS 是否匹配，且不要同时开启两种加密方式。"


def _pop3_ssl_error_hint(exc: ssl.SSLError) -> str:
    """将 POP3 底层 SSL/TLS 错误转换为中文提示。"""
    message = str(exc).lower()
    if "wrong version number" in message:
        return (
            f"POP3 SSL/TLS 握手失败，当前使用的是“{_pop3_security_mode_text()}”，"
            f"这通常不是协议版本真的错误，而是端口与加密方式不匹配。{_pop3_security_recommendation()}"
        )
    if "ssl" in message or "tls" in message:
        return f"POP3 SSL/TLS 握手失败。{_pop3_security_recommendation()}"
    return f"POP3 建立安全连接失败：{exc}"


def _decode_header_value(value: str | None) -> str:
    """解码邮件头中的多段编码文本。"""
    if not value:
        return ""
    parts = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(_decode_bytes(chunk, charset))
        else:
            parts.append(chunk)
    return "".join(parts)


def _normalize_charset(charset: str | None) -> str:
    """将不规范字符集名称归一化到可解码值。"""
    if not charset:
        return "utf-8"
    normalized = charset.strip().lower()
    if normalized in {"unknown-8bit", "unknown_8bit", "8bit", "x-unknown", "unknown"}:
        return "utf-8"
    return charset


def _decode_bytes(payload: bytes, charset: str | None) -> str:
    """尽量以多种候选编码解码邮件字节内容。"""
    candidates = [_normalize_charset(charset), "utf-8", "gb18030", "gbk", "latin-1"]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return payload.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return payload.decode("utf-8", errors="ignore")


def _extract_text_body(message: Message) -> str:
    """优先提取纯文本正文，并跳过附件。"""
    if message.is_multipart():
        texts: list[str] = []
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition.lower():
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset()
                texts.append(_decode_bytes(payload, charset))
        return "\n".join(texts).strip()
    payload = message.get_payload(decode=True) or b""
    charset = message.get_content_charset()
    return _decode_bytes(payload, charset).strip()


def _open_smtp_connection() -> smtplib.SMTP:
    """按配置自动选择普通 SMTP 或 SSL SMTP 连接。"""
    use_ssl = settings.smtp_use_ssl or settings.smtp_port == 465
    if use_ssl:
        return smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
    return smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)


def _open_imap_connection() -> imaplib.IMAP4:
    """按配置自动选择普通 IMAP、STARTTLS 或 SSL IMAP 连接。"""
    use_ssl = settings.imap_use_ssl or settings.imap_port == 993
    if use_ssl:
        return imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)

    mailbox = imaplib.IMAP4(settings.imap_host, settings.imap_port)
    if settings.imap_use_tls:
        # 仅在明确要求 STARTTLS 时升级连接，避免把纯明文端口误当成 SSL 端口处理。
        mailbox.starttls()
    return mailbox


def _open_pop3_connection() -> poplib.POP3:
    """按配置自动选择普通 POP3、STLS 或 SSL POP3 连接。"""
    use_ssl = settings.pop3_use_ssl or settings.pop3_port == 995
    if use_ssl:
        return poplib.POP3_SSL(settings.pop3_host, settings.pop3_port, timeout=settings.smtp_timeout_seconds)

    mailbox = poplib.POP3(settings.pop3_host, settings.pop3_port, timeout=settings.smtp_timeout_seconds)
    if settings.pop3_use_tls:
        # 仅在明确要求 STLS 时升级连接，避免把普通 110 端口误按 SSL 直连处理。
        mailbox.stls()
    return mailbox


def _resolve_message_id(message: Message, raw_message: bytes, fallback_prefix: str) -> str:
    """优先使用邮件头 Message-ID，缺失时退化为内容哈希，保证跨协议去重稳定。"""
    header_message_id = _decode_header_value(message.get("Message-ID"))
    if header_message_id:
        return header_message_id
    digest = hashlib.sha256(raw_message).hexdigest()[:24]
    return f"{fallback_prefix}-{digest}"


def _build_mail_event_from_message(
    db: Session,
    state: MailScanState,
    raw_message: bytes,
    fallback_prefix: str,
) -> bool:
    """将原始邮件落库并尝试匹配业务动作。

    返回:
    - `True` 表示本封邮件已新落库；
    - `False` 表示该邮件因基线或重复被跳过。
    """
    message = email.message_from_bytes(raw_message)
    message_time = _message_datetime(message)
    if message_time and state.baseline_started_at and message_time <= state.baseline_started_at:
        # 基线之前的历史邮件不参与自动处理，避免系统接入初期误操作旧数据。
        return False

    message_id = _resolve_message_id(message, raw_message, fallback_prefix)
    existing = db.query(MailEvent).filter(MailEvent.message_id == message_id).first()
    if existing:
        return False

    subject = _decode_header_value(message.get("Subject"))
    from_addr = _decode_header_value(message.get("From"))
    body = _extract_text_body(message)

    matched_template = None
    templates = sort_templates(db.query(Template).filter(Template.template_kind == "MAIL_REPLY", Template.enabled.is_(True)).all())
    for template in templates:
        if template_matches(template, subject, body):
            matched_template = template
            break

    mail_event = MailEvent(
        message_id=message_id,
        from_addr=from_addr,
        subject=subject,
        body_digest=body[:1000],
        resolved_template_id=matched_template.id if matched_template else None,
        resolved_version=matched_template.version if matched_template else None,
        process_status="MATCHED" if matched_template else "UNMATCHED",
    )
    db.add(mail_event)
    db.flush()

    if matched_template:
        _apply_business_action(db, mail_event, matched_template, subject, body, from_addr)
    return True


def _mail_scan_state(db: Session) -> MailScanState:
    """获取或初始化唯一的邮箱扫描状态记录。"""
    state = db.query(MailScanState).filter(MailScanState.id == 1).first()
    if not state:
        state = MailScanState(id=1)
        db.add(state)
        db.flush()
    return state


def initialize_mail_scan_baseline(db: Session) -> dict[str, str]:
    """重置邮件扫描基线，避免首次扫描误处理历史邮件。"""
    state = _mail_scan_state(db)
    now = shanghai_now_naive()
    state.baseline_started_at = now
    state.last_scan_at = now
    db.commit()
    return {"status": "success", "message": f"已设置首次扫描基准时间为 {now.isoformat(sep=' ', timespec='seconds')}"}


def _message_datetime(message: Message) -> datetime | None:
    """从邮件头解析发信时间，并转换为上海本地无时区时间。"""
    value = message.get("Date")
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed is None:
        return None
    return to_shanghai_naive(parsed)


def _extract_sender_email(from_addr: str) -> str:
    """从发件人文本中提取邮箱地址并归一化。"""
    return parseaddr(from_addr)[1].strip().lower()


def _parse_date(text: str) -> datetime | None:
    """从自然语言文本中提取日期。"""
    match = DATE_PATTERN.search(text or "")
    if not match:
        return None
    year, month, day = (int(item) for item in match.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _find_task_id(subject: str, body: str) -> int | None:
    """从主题或正文中提取任务编号。"""
    for source in (subject, body):
        match = TASK_ID_PATTERN.search(source or "")
        if match:
            return int(match.group(1))
    return None


def _find_delay_request_id(subject: str, body: str) -> int | None:
    """从主题或正文中提取延期申请编号。"""
    for source in (subject, body):
        match = DELAY_REQUEST_ID_PATTERN.search(source or "")
        if match:
            return int(match.group(1))
    return None


def _first_matching_line(text: str, keywords: tuple[str, ...]) -> str:
    """在邮件前几行中查找包含关键词的第一行。"""
    for raw_line in (text or "").splitlines()[:20]:
        line = raw_line.strip().replace("?", ":")
        if any(keyword in line for keyword in keywords):
            return line
    return ""


def _append_mail_action(db: Session, mail_event_id: int, action_type: str, status: str, target_task_id: int | None, payload: dict) -> None:
    """记录邮件触发的业务动作结果，便于列表页与详情页回放。"""
    db.add(
        MailAction(
            mail_event_id=mail_event_id,
            action_type=action_type,
            target_task_id=target_task_id,
            action_status=status,
            action_result_json=json.dumps(payload, ensure_ascii=False),
        )
    )


def _derive_task_status_from_subtasks(task: Task, subtasks: list[TaskSubtask]) -> str:
    """根据子任务状态推导主任务状态。"""
    if not subtasks:
        return task.main_status
    active_statuses = {item.status for item in subtasks}
    if active_statuses and active_statuses <= {"done"}:
        return "done"
    if "in_progress" in active_statuses or "done" in active_statuses:
        return "in_progress"
    if active_statuses <= {"canceled"}:
        return "canceled"
    return "not_started"


def diagnose_mail_settings() -> dict[str, str]:
    """测试 SMTP 连通性与认证配置。"""
    if not settings.smtp_host or not settings.smtp_from_address:
        return {"status": "failed", "message": "请先配置 SMTP_HOST 与 SMTP_FROM_ADDRESS 后再测试。"}
    if settings.smtp_use_ssl and settings.smtp_use_tls:
        return {"status": "failed", "message": "SMTP_USE_SSL 与 SMTP_USE_TLS 不能同时开启，请保留一种加密方式后重试。"}

    try:
        with _open_smtp_connection() as server:
            if not isinstance(server, smtplib.SMTP_SSL):
                server.ehlo()
                if settings.smtp_use_tls:
                    server.starttls()
                    server.ehlo()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
        hint = _provider_hint()
        suffix = f" 提示：{hint}" if hint else ""
        return {"status": "success", "message": f"SMTP 连接与认证成功。{suffix}".strip()}
    except ssl.SSLError as exc:
        return {"status": "failed", "message": _smtp_ssl_error_hint(exc)}
    except socket.gaierror as exc:
        provider_hint = _provider_hint()
        hint = f"{_generic_hint()} {'提示：' + provider_hint if provider_hint else ''}".strip()
        return {"status": "failed", "message": f"SMTP 域名解析失败：{settings.smtp_host}，错误：{exc}。{hint}"}
    except socket.timeout:
        hint = _provider_hint() or _generic_hint()
        return {
            "status": "failed",
            "message": f"SMTP 连接超时（超过 {settings.smtp_timeout_seconds} 秒）：{settings.smtp_host}:{settings.smtp_port}。请检查网络或端口是否放通。{hint}",
        }
    except smtplib.SMTPAuthenticationError:
        provider_hint = _provider_hint() or "请确认 SMTP 用户名和密码是否正确。"
        return {"status": "failed", "message": f"SMTP 认证失败。{provider_hint}"}
    except smtplib.SMTPServerDisconnected:
        hint = _provider_hint() or "请检查是否正确匹配了 SSL/TLS 端口与加密方式。"
        return {"status": "failed", "message": f"SMTP 连接被服务器断开。{hint}"}
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "message": f"SMTP 测试失败：{exc}"}


def diagnose_inbox_settings() -> dict[str, str]:
    """测试当前收件协议的登录与访问能力。"""
    if _inbox_protocol() == "pop3":
        if not settings.pop3_host or not settings.pop3_user:
            return {"status": "failed", "message": "请先配置 POP3_HOST 与 POP3_USER 后再测试。"}
        if settings.pop3_use_ssl and settings.pop3_use_tls:
            return {"status": "failed", "message": "POP3_USE_SSL 与 POP3_USE_TLS 不能同时开启，请保留一种加密方式后重试。"}
        mailbox = None
        try:
            mailbox = _open_pop3_connection()
            mailbox.user(settings.pop3_user)
            mailbox.pass_(settings.pop3_password)
            return {"status": "success", "message": "POP3 连接与登录成功，可以正常读取收件箱。"}
        except ssl.SSLError as exc:
            return {"status": "failed", "message": _pop3_ssl_error_hint(exc)}
        except socket.gaierror as exc:
            return {"status": "failed", "message": f"POP3 域名解析失败：{settings.pop3_host}，错误：{exc}。请确认 POP3_HOST 是否填写正确。"}
        except socket.timeout:
            return {"status": "failed", "message": f"POP3 连接超时：{settings.pop3_host}:{settings.pop3_port}"}
        except poplib.error_proto as exc:
            return {"status": "failed", "message": f"POP3 登录失败：{exc}"}
        except Exception as exc:  # pragma: no cover
            return {"status": "failed", "message": f"POP3 测试失败：{exc}"}
        finally:
            if mailbox is not None:
                try:
                    mailbox.quit()
                except Exception:
                    pass

    if not settings.imap_host or not settings.imap_user:
        return {"status": "failed", "message": "请先配置 IMAP_HOST 与 IMAP_USER 后再测试。"}
    if settings.imap_use_ssl and settings.imap_use_tls:
        return {"status": "failed", "message": "IMAP_USE_SSL 与 IMAP_USE_TLS 不能同时开启，请保留一种加密方式后重试。"}
    try:
        with _open_imap_connection() as mailbox:
            mailbox.login(settings.imap_user, settings.imap_password)
            mailbox.select("INBOX")
        return {"status": "success", "message": "IMAP 连接与登录成功，可以正常读取收件箱。"}
    except ssl.SSLError as exc:
        return {"status": "failed", "message": _imap_ssl_error_hint(exc)}
    except socket.gaierror as exc:
        return {"status": "failed", "message": f"IMAP 域名解析失败：{settings.imap_host}，错误：{exc}。请确认 IMAP_HOST 是否填写正确。"}
    except socket.timeout:
        return {"status": "failed", "message": f"IMAP 连接超时：{settings.imap_host}:{settings.imap_port}"}
    except imaplib.IMAP4.error as exc:
        return {"status": "failed", "message": f"IMAP 登录失败：{exc}"}
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "message": f"IMAP 测试失败：{exc}"}


def diagnose_imap_settings() -> dict[str, str]:
    """兼容旧调用名，内部统一转到当前收件协议诊断。"""
    return diagnose_inbox_settings()


def _apply_task_status_from_mail(db: Session, mail_event: MailEvent, notify_type: str, sender: User, subject: str, body: str) -> None:
    """根据邮件内容更新任务状态。"""
    task_id = _find_task_id(subject, body)
    if not task_id:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, notify_type, "FAILED", None, {"reason": "邮件中未识别到任务ID"})
        return

    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, notify_type, "FAILED", task_id, {"reason": "任务不存在"})
        return

    membership = db.query(TaskMember).filter(TaskMember.task_id == task_id, TaskMember.user_id == sender.id).first()
    if not membership:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, notify_type, "FAILED", task_id, {"reason": "发送人不是任务成员"})
        return

    if task.state_locked:
        mail_event.process_status = "SKIPPED"
        _append_mail_action(db, mail_event.id, notify_type, "SKIPPED", task_id, {"reason": "任务状态已锁定"})
        return

    next_status = "done" if notify_type == "task_done" else "in_progress"
    previous_status = task.main_status
    sender_subtasks = (
        db.query(TaskSubtask)
        .filter(TaskSubtask.task_id == task.id, TaskSubtask.assignee_id == sender.id)
        .order_by(TaskSubtask.sort_order.asc())
        .all()
    )
    updated_subtask_ids: list[int] = []
    if sender_subtasks:
        for item in sender_subtasks:
            if item.status == "canceled":
                # 已取消的子任务不再受邮件回执影响。
                continue
            item.status = next_status
            updated_subtask_ids.append(item.id)
        task.main_status = _derive_task_status_from_subtasks(
            task,
            db.query(TaskSubtask).filter(TaskSubtask.task_id == task.id).all(),
        )
    else:
        # 未拆子任务时，仍沿用原有主任务状态回写逻辑。
        task.main_status = next_status
    if task.main_status == "done" and task.actual_minutes == 0:
        # 首次完成时补算实际耗时，避免后续重复覆盖人工修正数据。
        task.actual_minutes = max(int((shanghai_now_naive() - task.start_at).total_seconds() // 60), 0)
    db.add(
        TaskStatusEvent(
            task_id=task.id,
            from_status=previous_status,
            to_status=task.main_status,
            source="mail",
            remark=body[:500],
            operator_id=sender.id,
        )
    )
    mail_event.process_status = "APPLIED"
    _append_mail_action(
        db,
        mail_event.id,
        notify_type,
        "APPLIED",
        task.id,
        {
            "from_status": previous_status,
            "to_status": task.main_status,
            "updated_subtask_ids": updated_subtask_ids,
        },
    )


def _apply_delay_request_from_mail(db: Session, mail_event: MailEvent, sender: User, subject: str, body: str) -> None:
    """根据成员邮件创建延期申请，并通知管理员审批。"""
    task_id = _find_task_id(subject, body)
    proposed_deadline = _parse_date(body) or _parse_date(subject)
    if not task_id or proposed_deadline is None:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_request", "FAILED", task_id, {"reason": "未识别到任务ID或延期日期"})
        return

    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_request", "FAILED", task_id, {"reason": "任务不存在"})
        return

    membership = db.query(TaskMember).filter(TaskMember.task_id == task_id, TaskMember.user_id == sender.id).first()
    if not membership:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_request", "FAILED", task_id, {"reason": "发送人不是任务成员"})
        return

    request_obj = DelayRequest(
        task_id=task.id,
        applicant_id=sender.id,
        apply_reason=body[:1000],
        original_deadline=task.end_at,
        proposed_deadline=proposed_deadline,
    )
    db.add(request_obj)
    db.flush()

    from app.services.notifications import create_notification_with_recipients

    admin_ids = [item.id for item in db.query(User).filter(User.role == "admin", User.is_active.is_(True)).all()]
    extra_context = {
        "delay_request_id": request_obj.id,
        "applicant_name": sender.name,
        "proposed_deadline": proposed_deadline.strftime("%Y-%m-%d"),
        "apply_reason": body[:300],
    }
    create_notification_with_recipients(db, task.id, "email", "delay_approval", "", recipient_user_ids=admin_ids, extra_context=extra_context)
    create_notification_with_recipients(db, task.id, "qax", "delay_approval", "", recipient_user_ids=admin_ids, extra_context=extra_context)

    mail_event.process_status = "APPLIED"
    _append_mail_action(db, mail_event.id, "delay_request", "APPLIED", task.id, {"delay_request_id": request_obj.id, "proposed_deadline": proposed_deadline.strftime("%Y-%m-%d")})


def _parse_delay_approval(body: str, subject: str) -> tuple[str | None, datetime | None, str]:
    """从管理员邮件中解析同意/拒绝动作和审批日期。"""
    line = _first_matching_line(body, ("同意", "拒绝")) or _first_matching_line(subject, ("同意", "拒绝"))
    if not line:
        return None, None, ""
    action = "APPROVE" if "同意" in line else "REJECT"
    approved_deadline = _parse_date(line)
    return action, approved_deadline, line


def _apply_delay_approval_from_mail(db: Session, mail_event: MailEvent, sender: User, subject: str, body: str) -> None:
    """根据管理员邮件执行延期审批。"""
    if sender.role != "admin":
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_approve", "FAILED", None, {"reason": "发送人不是管理员"})
        return

    delay_request_id = _find_delay_request_id(subject, body)
    if not delay_request_id:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_approve", "FAILED", None, {"reason": "未识别到延期申请ID"})
        return

    request_obj = db.query(DelayRequest).filter(DelayRequest.id == delay_request_id).first()
    if not request_obj:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_approve", "FAILED", None, {"reason": "延期申请不存在"})
        return

    action, approved_deadline, remark = _parse_delay_approval(body, subject)
    if not action:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_approve", "FAILED", request_obj.task_id, {"reason": "未识别审批动作"})
        return
    if action == "APPROVE" and approved_deadline is None:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_approve", "FAILED", request_obj.task_id, {"reason": "同意延期时必须提供日期"})
        return

    try:
        result, updated = apply_delay_decision(
            db=db,
            request_obj=request_obj,
            admin_id=sender.id,
            request_id=mail_event.message_id,
            action=action,
            channel="mail",
            version=request_obj.version,
            remark=remark,
            approved_deadline=approved_deadline,
        )
        mail_event.process_status = "APPLIED" if result in {"APPLIED", "IDEMPOTENT_REPLAY"} else "SKIPPED"
        _append_mail_action(db, mail_event.id, "delay_approve", "APPLIED" if result in {"APPLIED", "IDEMPOTENT_REPLAY"} else "SKIPPED", updated.task_id, {"result": result, "delay_request_id": updated.id, "approval_status": updated.approval_status})
    except HTTPException as exc:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_approve", "FAILED", request_obj.task_id, {"reason": exc.detail})


def _apply_business_action(db: Session, mail_event: MailEvent, template: Template, subject: str, body: str, from_addr: str) -> None:
    """根据匹配到的回复模板，将邮件转成具体业务动作。"""
    sender_email = _extract_sender_email(from_addr)
    sender = db.query(User).filter(User.email == sender_email).first()
    if not sender:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, template.notify_type, "FAILED", None, {"reason": "未找到发件人对应用户"})
        return

    if template.notify_type == "task_done":
        _apply_task_status_from_mail(db, mail_event, "task_done", sender, subject, body)
    elif template.notify_type == "task_in_progress":
        _apply_task_status_from_mail(db, mail_event, "task_in_progress", sender, subject, body)
    elif template.notify_type == "delay_request":
        _apply_delay_request_from_mail(db, mail_event, sender, subject, body)
    elif template.notify_type == "delay_approve":
        _apply_delay_approval_from_mail(db, mail_event, sender, subject, body)
    else:
        mail_event.process_status = "MATCHED"
        _append_mail_action(db, mail_event.id, template.notify_type, "SKIPPED", None, {"reason": "模板类型暂不支持"})


def _poll_mailbox_via_imap(db: Session, state: MailScanState) -> dict[str, str | int]:
    """使用 IMAP 扫描未读邮件。"""
    if settings.imap_use_ssl and settings.imap_use_tls:
        return {"status": "failed", "message": "IMAP_USE_SSL 与 IMAP_USE_TLS 不能同时开启，请修正配置后重试。", "count": 0}

    with _open_imap_connection() as mailbox:
        mailbox.login(settings.imap_user, settings.imap_password)
        mailbox.select("INBOX")
        status, data = mailbox.search(None, "UNSEEN")
        if status != "OK":
            return {"status": "failed", "message": "IMAP 未能查询未读邮件。", "count": 0}

        message_numbers = [item for item in data[0].split() if item]
        unread_total = len(message_numbers)
        if settings.mail_inbox_max_scan > 0:
            message_numbers = message_numbers[-settings.mail_inbox_max_scan :]

        saved_count = 0
        for imap_id in message_numbers:
            fetch_status, raw_data = mailbox.fetch(imap_id, "(BODY.PEEK[])")
            if fetch_status != "OK" or not raw_data or not raw_data[0]:
                continue
            raw_message = raw_data[0][1]
            if _build_mail_event_from_message(db, state, raw_message, f"imap-{imap_id.decode()}"):
                saved_count += 1

        return {
            "status": "success",
            "message": f"本次通过 IMAP 扫描未读邮件 {len(message_numbers)} 封（总未读 {unread_total} 封），已落库 {saved_count} 封。",
            "count": saved_count,
        }


def _poll_mailbox_via_pop3(db: Session, state: MailScanState) -> dict[str, str | int]:
    """使用 POP3 拉取最近邮件。"""
    if settings.pop3_use_ssl and settings.pop3_use_tls:
        return {"status": "failed", "message": "POP3_USE_SSL 与 POP3_USE_TLS 不能同时开启，请修正配置后重试。", "count": 0}

    mailbox = _open_pop3_connection()
    try:
        mailbox.user(settings.pop3_user)
        mailbox.pass_(settings.pop3_password)
        _, listings, _ = mailbox.list()
        message_numbers = [int(line.split()[0]) for line in listings if line]
        total_count = len(message_numbers)
        if settings.mail_inbox_max_scan > 0:
            message_numbers = message_numbers[-settings.mail_inbox_max_scan :]

        saved_count = 0
        for message_number in message_numbers:
            _, lines, _ = mailbox.retr(message_number)
            raw_message = b"\r\n".join(lines)
            if _build_mail_event_from_message(db, state, raw_message, f"pop3-{message_number}"):
                saved_count += 1

        return {
            "status": "success",
            "message": f"本次通过 POP3 扫描最近邮件 {len(message_numbers)} 封（总邮件 {total_count} 封），已落库 {saved_count} 封。",
            "count": saved_count,
        }
    finally:
        try:
            mailbox.quit()
        except Exception:
            pass


def poll_mailbox(db: Session) -> dict[str, str | int]:
    """扫描邮箱未读邮件并写入系统。

    说明:
    - 首次运行只建立基线，不处理历史邮件；
    - 仅扫描未读邮件，并限制单次最大扫描数量；
    - 邮件成功匹配回复模板后会尝试触发对应业务动作。
    """
    if _inbox_protocol() == "pop3":
        if not settings.pop3_host or not settings.pop3_user:
            return {"status": "skipped", "message": "未配置 POP3，已跳过邮件收取。", "count": 0}
    elif not settings.imap_host or not settings.imap_user:
        return {"status": "skipped", "message": "未配置 IMAP，已跳过邮件收取。", "count": 0}

    try:
        state = _mail_scan_state(db)
        if state.baseline_started_at is None:
            now = shanghai_now_naive()
            state.baseline_started_at = now
            state.last_scan_at = now
            db.commit()
            return {
                "status": "initialized",
                "message": f"已初始化扫描基准时间 {now.isoformat(sep=' ', timespec='seconds')}，本次不处理历史邮件。",
                "count": 0,
            }

        result = _poll_mailbox_via_pop3(db, state) if _inbox_protocol() == "pop3" else _poll_mailbox_via_imap(db, state)
        if result.get("status") == "success":
            state.last_scan_at = shanghai_now_naive()
            db.commit()
        return result
    except socket.gaierror as exc:
        if _inbox_protocol() == "pop3":
            return {"status": "failed", "message": f"POP3 域名解析失败：{settings.pop3_host}，错误：{exc}", "count": 0}
        return {"status": "failed", "message": f"IMAP 域名解析失败：{settings.imap_host}，错误：{exc}", "count": 0}
    except socket.timeout:
        if _inbox_protocol() == "pop3":
            return {"status": "failed", "message": f"POP3 连接超时：{settings.pop3_host}:{settings.pop3_port}", "count": 0}
        return {"status": "failed", "message": f"IMAP 连接超时：{settings.imap_host}:{settings.imap_port}", "count": 0}
    except ssl.SSLError as exc:
        if _inbox_protocol() == "pop3":
            return {"status": "failed", "message": _pop3_ssl_error_hint(exc), "count": 0}
        return {"status": "failed", "message": _imap_ssl_error_hint(exc), "count": 0}
    except poplib.error_proto as exc:
        return {"status": "failed", "message": f"POP3 登录失败：{exc}", "count": 0}
    except imaplib.IMAP4.error as exc:
        return {"status": "failed", "message": f"IMAP 登录失败：{exc}", "count": 0}
    except Exception as exc:  # pragma: no cover
        db.rollback()
        return {"status": "failed", "message": f"邮件扫描失败：{exc}", "count": 0}


def send_mail_notification(to_address: str, subject: str, content: str) -> dict[str, str]:
    """发送一封系统通知邮件。"""
    if not settings.smtp_host or not settings.smtp_from_address:
        return {"status": "failed", "message": "未配置 SMTP，无法发送邮件。"}
    if not to_address:
        return {"status": "failed", "message": "缺少收件人地址，无法发送。"}
    if settings.smtp_use_ssl and settings.smtp_use_tls:
        return {"status": "failed", "message": "邮件发送失败：SMTP_USE_SSL 与 SMTP_USE_TLS 不能同时开启。"}

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address
    message["To"] = to_address
    message.set_content(content)

    try:
        with _open_smtp_connection() as server:
            if not isinstance(server, smtplib.SMTP_SSL):
                server.ehlo()
                if settings.smtp_use_tls:
                    server.starttls()
                    server.ehlo()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
        return {"status": "sent", "message": "邮件发送成功"}
    except ssl.SSLError as exc:
        return {"status": "failed", "message": f"邮件发送失败：{_smtp_ssl_error_hint(exc)}"}
    except socket.gaierror as exc:
        return {"status": "failed", "message": f"邮件发送失败：SMTP 域名解析失败：{settings.smtp_host}，{exc}。{_generic_hint()}"}
    except socket.timeout:
        hint = _provider_hint() or "请检查网络、端口或服务端响应。"
        return {"status": "failed", "message": f"邮件发送失败：SMTP 连接超时：{settings.smtp_host}:{settings.smtp_port}。{hint}"}
    except smtplib.SMTPAuthenticationError:
        return {"status": "failed", "message": "邮件发送失败：SMTP 认证失败。"}
    except smtplib.SMTPServerDisconnected:
        hint = _provider_hint() or "请检查 SSL/TLS 配置是否与端口匹配。"
        return {"status": "failed", "message": f"邮件发送失败：SMTP 连接被服务器断开。{hint}"}
    except Exception as exc:  # pragma: no cover
        return {"status": "failed", "message": f"邮件发送失败：{exc}"}
