from __future__ import annotations

"""邮件接入服务。

负责 SMTP 连通性检测、POP3/IMAP 收件、邮件正文解析、模板匹配以及
“邮件驱动任务状态 / 延期审批”的业务处理。SMTP 与 POP3 收发基于 zmail，
IMAP 仍使用标准库。
"""

import email
import hashlib
import html as html_lib
import imaplib
import json
import logging
import poplib
import re
import ssl
import smtplib
import socket
import threading
import zmail
from contextlib import contextmanager
from datetime import datetime, timedelta
from email import message_from_string
from typing import Iterator
from zmail.server import MailServer as ZmailMailServer, SMTPServer as ZmailSMTPServer
from email.header import decode_header
from email.message import EmailMessage, Message
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from zmail.mime import Mail as ZmailMime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ADMIN_ROLES
from app.models import DelayRequest, MailAction, MailEvent, MailScanState, Notification, NotificationRecipient, Task, TaskMember, TaskStatusEvent, TaskSubtask, Template, User
from app.services.delay import apply_delay_decision
from app.services.runtime_settings import load_host_ip_mappings, load_runtime_settings
from app.services.templates import _split_rule, select_reply_template, sort_templates, strip_reply_guides
from app.timeutils import shanghai_now_naive, to_shanghai_naive


DATE_PATTERN = re.compile(r"(20\d{2})(?:-|/|年)(\d{1,2})(?:-|/|月)(\d{1,2})(?:日)?")
TASK_ID_PATTERN = re.compile(
    r"(?:【\s*任务通知\s*[#＃]\s*(\d+)\s*】|任务通知\s*[#＃]\s*(\d+)|任务\s*(?:ID|编号)\s*[#:：]?\s*(\d+)|任务\s*[#＃]\s*(\d+))",
    re.IGNORECASE,
)
DELAY_REQUEST_ID_PATTERN = re.compile(r"(?:延期申请\s*(?:ID|编号)\s*[#:：]?\s*|延期申请\s*#\s*)(\d+)", re.IGNORECASE)
_MAIL_POLL_EXECUTION_LOCK = threading.Lock()
_MAIL_HEADER_FETCH = "BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT FROM DATE MIME-VERSION CONTENT-TYPE CONTENT-TRANSFER-ENCODING)]"
_MAIL_BODY_FETCH_BYTES = 64 * 1024
_POP3_BODY_PREVIEW_LINES = 400
logger = logging.getLogger(__name__)
PreparedMailTemplate = tuple[Template, tuple[str, ...], tuple[str, ...]]
TASK_REPLYABLE_NOTIFY_TYPES = ("task_created", "task_updated", "manual_remind", "due_remind")


def _mail_inbox_folder_names() -> list[str]:
    raw = str(getattr(settings, "mail_inbox_folders", "") or "").strip()
    names = [item.strip().strip('"') for item in re.split(r"[,;\n\r|\u3001\uff0c\uff1b]+", raw) if item.strip()]
    return names or ["INBOX"]


def _is_default_inbox_folder(folder: str) -> bool:
    return (folder or "").strip().strip('"').upper() == "INBOX"


def _encode_imap_utf7(value: str) -> str:
    result: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        import base64

        raw = "".join(buffer).encode("utf-16-be")
        result.append("&" + base64.b64encode(raw).decode("ascii").rstrip("=").replace("/", ",") + "-")
        buffer.clear()

    for char in value:
        codepoint = ord(char)
        if 0x20 <= codepoint <= 0x7E:
            flush_buffer()
            result.append("&-" if char == "&" else char)
        else:
            buffer.append(char)
    flush_buffer()
    return "".join(result)


def _imap_mailbox_arg(folder: str) -> str:
    encoded = _encode_imap_utf7((folder or "INBOX").strip() or "INBOX")
    escaped = encoded.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _mailbox_fallback_prefix(protocol: str, folder: str, message_number: object) -> str:
    folder_key = re.sub(r"[^A-Za-z0-9_.-]+", "-", (folder or "INBOX").strip()).strip("-") or "INBOX"
    return f"{protocol}-{folder_key}-{message_number}"


def _try_select_pop3_folder(pop: object, folder: str) -> bool:
    if _is_default_inbox_folder(folder):
        return True
    targets: list[object] = [pop]
    raw_server = getattr(pop, "server", None)
    if raw_server is not None and raw_server is not pop:
        targets.append(raw_server)
    for target in targets:
        for method_name in ("select_folder", "select", "mailbox", "folder", "cwd"):
            method = getattr(target, method_name, None)
            if not callable(method):
                continue
            try:
                response = method(folder)
            except (AttributeError, NotImplementedError, poplib.error_proto):
                continue
            except TypeError:
                continue
            if isinstance(response, tuple) and response and isinstance(response[0], (bytes, str)):
                status = response[0].decode("utf-8", "ignore") if isinstance(response[0], bytes) else response[0]
                if status.strip().startswith("-"):
                    continue
            return True
    return False


def _mail_host_ip_overrides() -> dict[str, str]:
    return load_host_ip_mappings()


def _normalize_mail_address(value: str) -> str:
    return (parseaddr(value or "")[1] or value or "").strip().lower()


def _decoded_address_header(value: object) -> str:
    text = _decode_header_value(value)
    addresses = [addr.strip().lower() for _, addr in getaddresses([text]) if addr.strip()]
    return ",".join(addresses) if addresses else text.strip()


def _address_list_contains(value: str, target: str) -> bool:
    normalized_target = _normalize_mail_address(target)
    if not normalized_target:
        return False
    addresses = [addr.strip().lower() for _, addr in getaddresses([value or ""]) if addr.strip()]
    if not addresses:
        addresses = [item.strip().lower() for item in re.split(r"[,;\s]+", value or "") if item.strip()]
    return normalized_target in addresses


@contextmanager
def _patched_mail_dns_resolution() -> Iterator[dict[str, str]]:
    """Resolve configured mail hostnames to fixed IPs without changing system DNS."""

    overrides = _mail_host_ip_overrides()
    if not overrides:
        yield overrides
        return

    original_getaddrinfo = socket.getaddrinfo

    def mapped_getaddrinfo(host: object, port: object, *args: object, **kwargs: object) -> list[tuple]:
        mapped_host = overrides.get(str(host).strip().lower()) if host is not None else None
        return original_getaddrinfo(mapped_host or host, port, *args, **kwargs)

    socket.getaddrinfo = mapped_getaddrinfo  # type: ignore[assignment]
    try:
        yield overrides
    finally:
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]


def _mark_notification_recipient_replied(
    db: Session,
    task_id: int | None,
    user_id: int,
    mail_event: MailEvent,
    notify_types: tuple[str, ...],
) -> int | None:
    """在收到回复邮件后，将最匹配的邮件通知接收人标记为“已回复”。

    说明：
    - 这里只处理邮件渠道，因为“回复”动作来源于回信；
    - 同一成员可能收到多封同任务通知，这里优先回写回复邮件发生前最近的一封；
    - 返回命中的通知接收人编号，方便后续写入动作结果或测试断言。
    """
    if task_id is None:
        return None
    recipient = (
        db.query(NotificationRecipient)
        .join(Notification, NotificationRecipient.notification_id == Notification.id)
        .filter(
            Notification.task_id == task_id,
            Notification.channel == "email",
            Notification.notify_type.in_(notify_types),
            NotificationRecipient.user_id == user_id,
            Notification.created_at <= mail_event.created_at,
        )
        .order_by(Notification.created_at.desc(), Notification.id.desc(), NotificationRecipient.id.desc())
        .first()
    )
    if not recipient:
        return None
    # 收到成员回信后，无论业务动作是否真正推进，都说明这封通知已经得到成员反馈。
    recipient.read_status = "read"
    return recipient.id


def _leading_nonempty_lines(text: str, limit: int = 8) -> list[str]:
    """提取邮件开头的非空行，用于识别用户是否给出了明确回复指令。"""
    lines: list[str] = []
    for raw_line in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _reply_line_starts_with_keyword(line: str, keyword: str) -> bool:
    """Only treat a leading status keyword as a reply command."""
    normalized = (line or "").strip()
    normalized = re.sub(r"^(?:(?:re|fw|fwd|回复|答复)\s*[:：]\s*)+", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.lstrip(" \t\"'“‘【[（(")
    return normalized.lower().startswith((keyword or "").strip().lower())


def _first_explicit_reply_line(subject: str, body: str, keywords: tuple[str, ...]) -> str:
    """Return the first leading line whose status keyword is explicit."""
    candidates = [(subject or "").strip(), *_leading_nonempty_lines(body)]
    for line in candidates:
        if line and any(_reply_line_starts_with_keyword(line, keyword) for keyword in keywords):
            return line
    return ""


def _find_explicit_reply_line(subject: str, body: str, keywords: tuple[str, ...]) -> str:
    """仅在主题或正文前几行中查找明确回复指令，避免把系统通知正文误判成回信。"""
    normalized_subject = (subject or "").strip()
    if normalized_subject and any(keyword in normalized_subject for keyword in keywords):
        return normalized_subject
    for line in _leading_nonempty_lines(body):
        if any(keyword in line for keyword in keywords):
            return line
    return ""


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
    - 这里统一转成“当前配置 + 推荐配置”的形式，便于运维在系统设置中调整。
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


def _smtp_protocol_error_hint(exc: Exception) -> str:
    """将 SMTP 协议层异常转换成更可操作的提示。"""
    message = str(exc)
    normalized = message.lower()
    host = settings.smtp_host.lower().strip()
    if "line too long" in normalized:
        return (
            "SMTP 发件失败：服务端返回了非标准 SMTP 响应（line too long）。"
            "这通常是把 POP3/IMAP 主机或端口误用于发件，或被内网邮件网关转发到了错误协议。"
            "POP3 不能用于发件，请改用 SMTP_HOST/SMTP_PORT，并检查端口与 SSL/TLS 是否匹配。"
        )
    if host.startswith("pop.") or host.startswith("pop3.") or "pop3" in host:
        return "SMTP 发件失败：当前 SMTP_HOST 看起来是 POP3 地址。POP3 只能收件，发件请改用 SMTP 地址。"
    if host.startswith("imap.") or "imap" in host:
        return "SMTP 发件失败：当前 SMTP_HOST 看起来是 IMAP 地址。IMAP 只能收件，发件请改用 SMTP 地址。"
    return f"SMTP 发件失败：{exc}"


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


def _pop3_protocol_error_hint(exc: poplib.error_proto) -> str:
    """将 POP3 协议层错误转换成更可操作的提示。"""
    message = str(exc)
    normalized = message.lower()
    if "line too long" in normalized:
        return (
            f"POP3 登录失败：服务端返回了非标准 POP3 响应（line too long）。"
            f"这通常不是账号密码错误，而是 POP3_HOST、POP3_PORT 与加密方式不匹配，"
            f"当前使用的是“{_pop3_security_mode_text()}”。{_pop3_security_recommendation()}"
        )
    return f"POP3 登录失败：{exc}"


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
    """优先提取纯文本正文，并在必要时退回 HTML 正文。

    有些邮箱客户端只返回 `text/html`，如果这里直接忽略会导致落库邮件没有正文，
    既影响模板匹配，也会让详情页只能看到零碎摘要。
    """
    if message.is_multipart():
        texts: list[str] = []
        html_texts: list[str] = []
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition.lower():
                continue
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset()
            if content_type == "text/plain":
                texts.append(_decode_bytes(payload, charset))
            elif content_type == "text/html":
                html_texts.append(_html_to_plain_text(_decode_bytes(payload, charset)))
        if texts:
            return "\n".join(texts).strip()
        return "\n".join(html_texts).strip()
    payload = message.get_payload(decode=True) or b""
    charset = message.get_content_charset()
    content = _decode_bytes(payload, charset).strip()
    if message.get_content_type() == "text/html":
        return _html_to_plain_text(content)
    return content


def _html_to_plain_text(content: str) -> str:
    """把 HTML 正文转换为适合匹配和展示的纯文本。

    - 先把常见换行标签转成真正换行，避免整段内容黏成一行。
    - 再去掉剩余标签并解码 `&nbsp;` 等实体，统一输出可读文本。
    """
    normalized = re.sub(r"(?i)<br\s*/?>", "\n", content or "")
    normalized = re.sub(r"(?i)</p\s*>", "\n", normalized)
    normalized = re.sub(r"(?i)<p[^>]*>", "", normalized)
    normalized = re.sub(r"(?i)</div\s*>", "\n", normalized)
    normalized = re.sub(r"(?i)<div[^>]*>", "", normalized)
    normalized = re.sub(r"(?is)<style.*?>.*?</style>", "", normalized)
    normalized = re.sub(r"(?is)<script.*?>.*?</script>", "", normalized)
    normalized = re.sub(r"(?s)<[^>]+>", "", normalized)
    normalized = html_lib.unescape(normalized).replace("\xa0", " ")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _plain_text_to_html(content: str) -> str:
    """把系统正文转成兼容邮件客户端的 HTML 版本。

    仅发送 `text/plain` 时，部分邮箱会自行按 HTML 渲染并折叠空格与换行。
    这里补充 HTML alternative，让客户端按预期保留段落和空白。
    """
    escaped = html_lib.escape(content or "")
    escaped = escaped.replace(" ", "&nbsp;").replace("\n", "<br>")
    return (
        "<html><body>"
        "<div style=\"font-family:Microsoft YaHei,Segoe UI,sans-serif;"
        "font-size:14px;line-height:1.8;color:#172033;\">"
        f"{escaped}"
        "</div></body></html>"
    )


def _smtp_login_username() -> str:
    """返回 zmail 需要使用的 SMTP 登录用户名。"""

    return (settings.smtp_user or settings.smtp_from_address).strip()


def _make_zmail_smtp_server() -> ZmailSMTPServer:
    """按当前配置构造 zmail SMTPServer。"""

    return ZmailSMTPServer(
        username=_smtp_login_username(),
        password=settings.smtp_password,
        host=settings.smtp_host,
        port=settings.smtp_port,
        ssl=_smtp_ssl_flag(),
        tls=settings.smtp_use_tls,
        timeout=settings.smtp_timeout_seconds,
        debug=False,
    )


@contextmanager
def _open_smtp_connection() -> Iterator[ZmailSMTPServer]:
    """统一通过 zmail SMTPServer 打开 SMTP 连接。"""

    server = _make_zmail_smtp_server()
    with _patched_mail_dns_resolution():
        if settings.smtp_user:
            with server as opened_server:
                yield opened_server
            return

        server._make_server()
        try:
            if server.tls:
                server.stls()
            yield server
        finally:
            if server.server is not None:
                try:
                    server.server.quit()
                except smtplib.SMTPServerDisconnected:
                    pass
                finally:
                    try:
                        server.server.close()
                    except Exception:
                        pass
                    server._remove_server()


def _open_imap_connection() -> imaplib.IMAP4:
    """按配置自动选择普通 IMAP、STARTTLS 或 SSL IMAP 连接。"""
    use_ssl = settings.imap_use_ssl or settings.imap_port == 993
    with _patched_mail_dns_resolution():
        if use_ssl:
            return imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)

        mailbox = imaplib.IMAP4(settings.imap_host, settings.imap_port)
        if settings.imap_use_tls:
            # 仅在明确要求 STARTTLS 时升级连接，避免把纯明文端口误当成 SSL 端口处理。
            mailbox.starttls()
        return mailbox


def _smtp_ssl_flag() -> bool:
    return settings.smtp_use_ssl or settings.smtp_port == 465


def _pop3_ssl_flag() -> bool:
    return settings.pop3_use_ssl or settings.pop3_port == 995


def _make_zmail_mail_server(username: str, password: str) -> ZmailMailServer:
    """按当前 SMTP/POP3 配置构造 zmail MailServer（POP 与 SMTP 使用同一套主机与端口参数）。"""
    return zmail.server(
        username,
        password,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_ssl=_smtp_ssl_flag(),
        smtp_tls=settings.smtp_use_tls,
        pop_host=settings.pop3_host,
        pop_port=settings.pop3_port,
        pop_ssl=_pop3_ssl_flag(),
        pop_tls=settings.pop3_use_tls,
        timeout=settings.smtp_timeout_seconds,
    )


def _resolve_message_id(message: Message, raw_message: bytes, fallback_prefix: str) -> str:
    """优先使用邮件头 Message-ID，缺失时退化为内容哈希，保证跨协议去重稳定。"""
    header_message_id = _decode_header_value(message.get("Message-ID"))
    if header_message_id:
        return header_message_id
    digest = hashlib.sha256(raw_message).hexdigest()[:24]
    return f"{fallback_prefix}-{digest}"


def _extract_imap_fetch_bytes(raw_data: object) -> bytes:
    """Return the first bytes payload from an IMAP fetch response."""
    if not raw_data:
        return b""
    if isinstance(raw_data, (bytes, bytearray)):
        return bytes(raw_data)
    if not isinstance(raw_data, (list, tuple)):
        return b""
    for item in raw_data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
        if isinstance(item, (bytes, bytearray)) and b"\r\n" in item:
            return bytes(item)
    return b""


def _imap_since_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{value.day:02d}-{months[value.month - 1]}-{value.year}"


def _is_message_before_baseline(message: Message, state: MailScanState) -> bool:
    message_time = _message_datetime(message)
    return bool(message_time and state.baseline_started_at and message_time <= state.baseline_started_at)


def _mail_reply_templates(db: Session) -> list[PreparedMailTemplate]:
    templates = sort_templates(
        db.query(Template)
        .filter(
            Template.template_kind == "MAIL_REPLY",
            Template.enabled.is_(True),
            Template.notify_type.in_(("task_done", "task_in_progress")),
        )
        .all()
    )
    return [
        (
            template,
            tuple(rule.lower() for rule in _split_rule(template.subject_rule)),
            tuple(rule.lower() for rule in _split_rule(template.body_rule)),
        )
        for template in templates
    ]


def _match_mail_template(templates: list[PreparedMailTemplate], subject: str, body: str) -> Template | None:
    return select_reply_template([template for template, _, _ in templates], subject, body)


def _existing_mail_message_ids(db: Session, message_ids: list[str]) -> set[str]:
    if not message_ids:
        return set()
    rows = db.query(MailEvent.message_id).filter(MailEvent.message_id.in_(message_ids)).all()
    return {row[0] for row in rows}


def _processed_mail_message_ids(db: Session, message_ids: list[str]) -> set[str]:
    if not message_ids:
        return set()
    rows = (
        db.query(MailEvent.message_id)
        .filter(MailEvent.message_id.in_(message_ids), MailEvent.process_status != "UNMATCHED")
        .all()
    )
    return {row[0] for row in rows}


def _join_header_and_body_preview(header_bytes: bytes, body_bytes: bytes) -> bytes:
    if not header_bytes:
        return body_bytes
    for separator in (b"\r\n\r\n", b"\n\n"):
        if separator in header_bytes and header_bytes.split(separator, 1)[1].strip():
            return header_bytes
    separator = b"\r\n\r\n" if b"\r\n" in header_bytes else b"\n\n"
    return header_bytes.rstrip(b"\r\n") + separator + body_bytes.lstrip(b"\r\n")


def _pop3_top(pop: object, message_number: int, line_count: int) -> list[bytes]:
    server = getattr(pop, "server", pop)
    if not hasattr(server, "top") and hasattr(server, "get_mail"):
        lines = server.get_mail(message_number)
        return [line if isinstance(line, bytes) else str(line).encode("utf-8", errors="ignore") for line in lines]
    _, lines, _ = server.top(message_number, line_count)
    return [line if isinstance(line, bytes) else str(line).encode("utf-8", errors="ignore") for line in lines]


def _decode_imap_id(imap_id: bytes | str) -> str:
    return imap_id.decode() if isinstance(imap_id, bytes) else str(imap_id)


def _mail_subject_system_name() -> str:
    return "任务通知"


def _format_system_mail_subject(subject: str) -> str:
    system_name = _mail_subject_system_name()
    clean_subject = (subject or "").strip()
    if clean_subject.startswith("【任务通知#") or not system_name or system_name in clean_subject:
        return clean_subject
    return f"[{system_name}] {clean_subject}"


def _is_system_mail_subject(subject: str) -> bool:
    system_name = _mail_subject_system_name()
    text = subject or ""
    return text.startswith("【任务通知#") or text.startswith("任务#") or bool(system_name and system_name.lower() in text.lower())


def _safe_mail_text(value: object, *, limit: int, field_name: str) -> str:
    """将待落库文本收敛为安全字符串，避免异常类型或超长内容拖垮整次收件。"""

    text = value if isinstance(value, str) else ("" if value is None else str(value))
    if len(text) <= limit:
        return text
    logger.warning("Mail field %s exceeded limit %s and was truncated", field_name, limit)
    return text[:limit]


def _record_failed_mail_event(
    db: Session,
    *,
    message_id: str,
    from_addr: str,
    subject: str,
    raw_message: bytes,
    reason: str,
) -> None:
    """尽量落一条失败邮件记录，便于排查单封异常但不影响后续邮件继续处理。"""

    safe_message_id = _safe_mail_text(message_id, limit=255, field_name="message_id")
    if db.query(MailEvent).filter(MailEvent.message_id == safe_message_id).first():
        return

    digest = hashlib.sha256(raw_message).hexdigest()
    detail = _safe_mail_text(reason, limit=1000, field_name="body_digest")
    original = _safe_mail_text(
        f"RAW_SHA256={digest}\nERROR={reason}",
        limit=10000,
        field_name="original_body",
    )
    failed_event = MailEvent(
        message_id=safe_message_id,
        from_addr=_safe_mail_text(from_addr, limit=255, field_name="from_addr"),
        subject=_safe_mail_text(subject, limit=2000, field_name="subject"),
        body_digest=detail,
        original_body=original,
        resolved_template_id=None,
        resolved_version=None,
        process_status="FAILED",
    )
    db.add(failed_event)
    db.flush()


def _build_mail_event_from_message(
    db: Session,
    state: MailScanState,
    raw_message: bytes,
    fallback_prefix: str,
    inbox_protocol: str = "",
    inbox_folder: str = "",
    server_message_ref: str = "",
    templates: list[PreparedMailTemplate] | None = None,
    known_message_id: str | None = None,
    skip_existing_check: bool = False,
    replace_unmatched_existing: bool = False,
) -> bool:
    """将原始邮件落库并尝试匹配业务动作。

    返回:
    - `True` 表示本封邮件已新落库；
    - `False` 表示该邮件因基线或重复被跳过。
    """
    message = email.message_from_bytes(raw_message)
    if _is_message_before_baseline(message, state):
        # 基线之前的历史邮件不参与自动处理，避免系统接入初期误操作旧数据。
        return False

    message_id = known_message_id or _resolve_message_id(message, raw_message, fallback_prefix)
    existing = db.query(MailEvent).filter(MailEvent.message_id == message_id).first()
    if existing and not (replace_unmatched_existing and existing.process_status == "UNMATCHED"):
        if skip_existing_check:
            return False
        return False

    subject = _decode_header_value(message.get("Subject"))
    from_addr = _decode_header_value(message.get("From"))
    to_addr = _decoded_address_header(message.get("To"))
    body = _extract_text_body(message)

    matched_template = _match_mail_template(templates if templates is not None else _mail_reply_templates(db), subject, body)

    if existing and existing.process_status == "UNMATCHED":
        mail_event = existing
        mail_event.from_addr = from_addr
        mail_event.to_addr = to_addr
        mail_event.subject = subject
        mail_event.body_digest = body[:1000]
        mail_event.original_body = body
        mail_event.inbox_protocol = inbox_protocol
        mail_event.inbox_folder = inbox_folder
        mail_event.server_message_ref = server_message_ref
        mail_event.resolved_template_id = matched_template.id if matched_template else None
        mail_event.resolved_version = matched_template.version if matched_template else None
        mail_event.process_status = "MATCHED" if matched_template else "UNMATCHED"
    else:
        mail_event = MailEvent(
            message_id=message_id,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            body_digest=body[:1000],
            original_body=body,
            inbox_protocol=inbox_protocol,
            inbox_folder=inbox_folder,
            server_message_ref=server_message_ref,
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


def initialize_mail_scan_baseline(db: Session, baseline_at: datetime | None = None) -> dict[str, str]:
    """重置邮件扫描基线，避免首次扫描误处理历史邮件。"""
    state = _mail_scan_state(db)
    now = baseline_at or shanghai_now_naive()
    state.baseline_started_at = now
    state.last_scan_at = now
    db.commit()
    return {"status": "success", "message": f"已设置首次扫描基准时间为 {now.isoformat(sep=' ', timespec='seconds')}"}


@contextmanager
def _mail_poll_guard() -> Iterator[bool]:
    """避免自动收件与手动收件并发执行，导致 POP3 邮箱锁冲突或前端长时间等待。"""

    acquired = _MAIL_POLL_EXECUTION_LOCK.acquire(blocking=False)
    try:
        yield acquired
    finally:
        if acquired:
            _MAIL_POLL_EXECUTION_LOCK.release()


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
            for group in match.groups():
                if group:
                    return int(group)
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


def _delete_imap_message(folder: str, server_message_ref: str) -> None:
    with _open_imap_connection() as mailbox:
        mailbox.login(settings.imap_user, settings.imap_password)
        status, _ = mailbox.select(_imap_mailbox_arg(folder or "INBOX"))
        if status != "OK":
            raise RuntimeError(f"IMAP folder unavailable: {folder or 'INBOX'}")
        message_ref = str(server_message_ref or "").strip()
        if not message_ref:
            raise RuntimeError("IMAP server message ref is empty")
        store_status, _ = mailbox.store(message_ref, "+FLAGS", r"(\Deleted)")
        if store_status != "OK":
            raise RuntimeError(f"IMAP delete failed: {message_ref}")
        mailbox.expunge()


def _delete_pop3_message(folder: str, server_message_ref: str) -> None:
    mail_server = _make_zmail_mail_server(settings.pop3_user, settings.pop3_password)
    with _patched_mail_dns_resolution(), mail_server.pop_server as pop:
        target_folder = (folder or "INBOX").strip() or "INBOX"
        if not _try_select_pop3_folder(pop, target_folder) and not _is_default_inbox_folder(target_folder):
            raise RuntimeError(f"POP3 folder unavailable: {target_folder}")
        message_number = int(str(server_message_ref or "").strip())
        server = getattr(pop, "server", pop)
        stat_method = getattr(server, "stat", None) or getattr(pop, "stat", None)
        if callable(stat_method):
            stat_method()
        server.dele(message_number)


def _delete_mail_event_message(event: MailEvent) -> None:
    if event.inbox_protocol == "imap":
        _delete_imap_message(event.inbox_folder, event.server_message_ref)
    elif event.inbox_protocol == "pop3":
        _delete_pop3_message(event.inbox_folder, event.server_message_ref)
    else:
        raise RuntimeError(f"Unsupported inbox protocol: {event.inbox_protocol or '-'}")


def _is_original_notification_mail_for_reply(event: MailEvent, *, task_id: int, reply_sender: str) -> bool:
    if not event.server_message_ref or event.inbox_protocol not in {"imap", "pop3"}:
        return False
    if _find_task_id(event.subject, event.original_body or event.body_digest) != task_id:
        return False
    system_from = _normalize_mail_address(settings.smtp_from_address or settings.smtp_user)
    event_from = _normalize_mail_address(event.from_addr)
    if system_from and event_from != system_from:
        return False
    return _address_list_contains(event.to_addr, reply_sender)


def cleanup_applied_task_reply_mails(db: Session) -> dict[str, object]:
    """删除已成功应用的回复邮件，以及同一成员对应的原始任务通知邮件。"""

    rows = (
        db.query(MailAction, MailEvent)
        .join(MailEvent, MailEvent.id == MailAction.mail_event_id)
        .filter(
            MailAction.action_type.in_(("task_in_progress", "task_done")),
            MailAction.action_status.in_(("APPLIED", "SUCCESS")),
            MailAction.target_task_id.isnot(None),
            MailEvent.server_message_ref != "",
            MailEvent.inbox_protocol.in_(("imap", "pop3")),
        )
        .order_by(MailAction.id.asc())
        .all()
    )
    deleted_ids: list[int] = []
    failed: list[dict[str, object]] = []
    seen_event_ids: set[int] = set()

    def delete_event(event: MailEvent, reason: str) -> None:
        if event.id in seen_event_ids or not event.server_message_ref:
            return
        seen_event_ids.add(event.id)
        try:
            _delete_mail_event_message(event)
            event.server_message_ref = ""
            deleted_ids.append(event.id)
        except Exception as exc:  # pragma: no cover - depends on real mailbox server behavior
            failed.append({"mail_event_id": event.id, "reason": reason, "error": str(exc)})

    for action, reply_event in rows:
        task_id = int(action.target_task_id or 0)
        reply_sender = _normalize_mail_address(reply_event.from_addr)
        original_events = (
            db.query(MailEvent)
            .filter(
                MailEvent.id != reply_event.id,
                MailEvent.server_message_ref != "",
                MailEvent.inbox_protocol == reply_event.inbox_protocol,
            )
            .order_by(MailEvent.id.desc())
            .all()
        )
        for original_event in original_events:
            if _is_original_notification_mail_for_reply(original_event, task_id=task_id, reply_sender=reply_sender):
                delete_event(original_event, "original_notification")
        delete_event(reply_event, "matched_reply")

    return {
        "status": "success" if not failed else "partial_failed",
        "deleted_count": len(deleted_ids),
        "deleted_mail_event_ids": deleted_ids,
        "failed_count": len(failed),
        "failures": failed,
    }


def delete_task_related_mail_from_inbox(db: Session, task_id: int) -> dict[str, object]:
    action_event_ids = {
        event_id
        for (event_id,) in (
            db.query(MailAction.mail_event_id)
            .filter(MailAction.target_task_id == task_id)
            .distinct()
            .all()
        )
    }
    candidates = (
        db.query(MailEvent)
        .filter(
            MailEvent.server_message_ref != "",
            MailEvent.inbox_protocol.in_(("imap", "pop3")),
        )
        .order_by(MailEvent.id.asc())
        .all()
    )
    events = [
        event
        for event in candidates
        if event.id in action_event_ids
        or _find_task_id(event.subject, event.original_body or event.body_digest) == task_id
    ]
    deleted_ids: list[int] = []
    skipped_ids: list[int] = []
    failed: list[dict[str, object]] = []
    seen_message_ids: set[str] = set()

    for event in events:
        if event.message_id in seen_message_ids:
            continue
        seen_message_ids.add(event.message_id)
        try:
            if event.inbox_protocol == "imap":
                _delete_imap_message(event.inbox_folder, event.server_message_ref)
            elif event.inbox_protocol == "pop3":
                _delete_pop3_message(event.inbox_folder, event.server_message_ref)
            else:
                skipped_ids.append(event.id)
                continue
            deleted_ids.append(event.id)
        except Exception as exc:  # pragma: no cover
            failed.append({"mail_event_id": event.id, "message_id": event.message_id, "reason": str(exc)})

    deleted_record_count = 0
    deleted_action_count = 0
    if deleted_ids:
        deleted_action_count = db.query(MailAction).filter(MailAction.mail_event_id.in_(deleted_ids)).delete(synchronize_session=False)
        deleted_record_count = db.query(MailEvent).filter(MailEvent.id.in_(deleted_ids)).delete(synchronize_session=False)

    result: dict[str, object] = {
        "task_id": task_id,
        "matched_count": len(events),
        "deleted_count": len(deleted_ids),
        "deleted_mail_event_ids": deleted_ids,
        "deleted_record_count": deleted_record_count,
        "deleted_action_count": deleted_action_count,
        "skipped_count": len(skipped_ids),
        "skipped_mail_event_ids": skipped_ids,
        "failed_count": len(failed),
        "failures": failed,
    }
    if deleted_ids:
        logger.info("Deleted inbox mails for task %s: %s", task_id, result)
    elif failed:
        logger.warning("Delete inbox mails for task %s failed: %s", task_id, result)
    return result


def cleanup_completed_task_mails(db: Session, retention_days: int) -> dict[str, object]:
    """按保留天数批量清理已完成任务对应的成员回执邮件。"""

    safe_days = max(int(retention_days or 30), 1)
    cutoff = shanghai_now_naive() - timedelta(days=safe_days)
    tasks = (
        db.query(Task)
        .filter(
            Task.deleted_at.is_(None),
            Task.main_status == "done",
            Task.completed_at.isnot(None),
            Task.completed_at <= cutoff,
        )
        .order_by(Task.completed_at.asc(), Task.id.asc())
        .all()
    )
    task_results: list[dict[str, object]] = []
    deleted_count = 0
    deleted_record_count = 0
    deleted_action_count = 0
    failed_count = 0
    for task in tasks:
        result = delete_task_related_mail_from_inbox(db, task.id)
        task_results.append(result)
        deleted_count += int(result.get("deleted_count") or 0)
        deleted_record_count += int(result.get("deleted_record_count") or 0)
        deleted_action_count += int(result.get("deleted_action_count") or 0)
        failed_count += int(result.get("failed_count") or 0)
    return {
        "status": "success" if failed_count == 0 else "partial_failed",
        "retention_days": safe_days,
        "cutoff": cutoff.isoformat(sep=" ", timespec="seconds"),
        "task_count": len(tasks),
        "deleted_count": deleted_count,
        "deleted_record_count": deleted_record_count,
        "deleted_action_count": deleted_action_count,
        "failed_count": failed_count,
        "task_results": task_results,
    }


def _member_has_done_reply(db: Session, task_id: int, user: User | None) -> bool:
    if not user:
        return False
    return (
        db.query(MailAction)
        .join(MailEvent, MailEvent.id == MailAction.mail_event_id)
        .filter(
            MailAction.target_task_id == task_id,
            MailAction.action_type == "task_done",
            MailAction.action_status.in_(["SUCCESS", "APPLIED"]),
            MailEvent.from_addr == user.email,
        )
        .first()
        is not None
    )


def _member_has_progress_reply(db: Session, task_id: int, user: User | None) -> bool:
    if not user:
        return False
    return (
        db.query(MailAction)
        .join(MailEvent, MailEvent.id == MailAction.mail_event_id)
        .filter(
            MailAction.target_task_id == task_id,
            MailAction.action_type.in_(["task_done", "task_in_progress"]),
            MailAction.action_status.in_(["SUCCESS", "APPLIED"]),
            MailEvent.from_addr == user.email,
        )
        .first()
        is not None
    )


def _derive_task_status_from_subtasks(
    db: Session,
    task: Task,
    subtasks: list[TaskSubtask],
    *,
    current_user_id: int | None = None,
    current_status: str | None = None,
) -> str:
    """根据子任务状态推导主任务状态。"""
    members = db.query(TaskMember).filter(TaskMember.task_id == task.id).all()
    if not members:
        return task.main_status
    subtasks_by_member: dict[int, list[TaskSubtask]] = {}
    for item in subtasks:
        if item.status == "canceled":
            continue
        subtasks_by_member.setdefault(item.assignee_id, []).append(item)

    all_complete = True
    any_progress = False
    for member in members:
        member_subtasks = subtasks_by_member.get(member.user_id, [])
        if member_subtasks:
            statuses = {item.status for item in member_subtasks}
            member_complete = bool(statuses) and statuses <= {"done"}
            member_progress = "in_progress" in statuses or "done" in statuses
        else:
            member_complete = (
                member.user_id == current_user_id and current_status == "done"
            ) or _member_has_done_reply(db, task.id, member.user)
            member_progress = (
                member.user_id == current_user_id and current_status in {"done", "in_progress"}
            ) or _member_has_progress_reply(db, task.id, member.user)
        all_complete = all_complete and member_complete
        any_progress = any_progress or member_progress

    if all_complete:
        return "done"
    if any_progress:
        return "in_progress"
    return "not_started"


def diagnose_mail_settings() -> dict[str, str]:
    """测试 SMTP 连通性与认证配置。"""
    if not settings.smtp_host or not settings.smtp_from_address:
        return {"status": "failed", "message": "请先配置 SMTP_HOST 与 SMTP_FROM_ADDRESS 后再测试。"}
    if settings.smtp_use_ssl and settings.smtp_use_tls:
        return {"status": "failed", "message": "SMTP_USE_SSL 与 SMTP_USE_TLS 不能同时开启，请保留一种加密方式后重试。"}

    try:
        with _open_smtp_connection():
            pass
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
    """Test login and folder access for the currently enabled inbox protocol."""
    folders = _mail_inbox_folder_names()
    if _inbox_protocol() == "pop3":
        if not settings.pop3_host or not settings.pop3_user:
            return {"status": "failed", "message": "请先配置 POP3_HOST 与 POP3_USER 后再测试。"}
        if settings.pop3_use_ssl and settings.pop3_use_tls:
            return {"status": "failed", "message": "POP3_USE_SSL 与 POP3_USE_TLS 不能同时开启，请保留一种加密方式后重试。"}
        try:
            mail_server = _make_zmail_mail_server(settings.pop3_user, settings.pop3_password)
            unsupported_folder = ""
            with _patched_mail_dns_resolution():
                with mail_server.pop_server as pop:
                    for folder in folders:
                        if not _try_select_pop3_folder(pop, folder):
                            unsupported_folder = folder
                            break
            if unsupported_folder:
                return {
                    "status": "success",
                    "message": f"POP3 连接与登录成功；当前 POP3 服务未暴露文件夹选择能力（{unsupported_folder}），实际收件将兼容扫描默认邮箱列表。",
                }
            return {"status": "success", "message": f"POP3 连接与登录成功，可读取配置的收件文件夹：{', '.join(folders)}。"}
        except ssl.SSLError as exc:
            return {"status": "failed", "message": _pop3_ssl_error_hint(exc)}
        except socket.gaierror as exc:
            return {"status": "failed", "message": f"POP3 域名解析失败：{settings.pop3_host}，错误：{exc}。请确认 POP3_HOST 是否填写正确。"}
        except socket.timeout:
            return {"status": "failed", "message": f"POP3 连接超时：{settings.pop3_host}:{settings.pop3_port}"}
        except poplib.error_proto as exc:
            return {"status": "failed", "message": _pop3_protocol_error_hint(exc)}
        except Exception as exc:  # pragma: no cover
            return {"status": "failed", "message": f"POP3 测试失败：{exc}"}

    if not settings.imap_host or not settings.imap_user:
        return {"status": "failed", "message": "请先配置 IMAP_HOST 与 IMAP_USER 后再测试。"}
    if settings.imap_use_ssl and settings.imap_use_tls:
        return {"status": "failed", "message": "IMAP_USE_SSL 与 IMAP_USE_TLS 不能同时开启，请保留一种加密方式后重试。"}
    try:
        with _open_imap_connection() as mailbox:
            mailbox.login(settings.imap_user, settings.imap_password)
            for folder in folders:
                status, _ = mailbox.select(_imap_mailbox_arg(folder))
                if status != "OK":
                    return {"status": "failed", "message": f"IMAP 文件夹无法访问：{folder}。请检查计划任务-收件配置中的文件夹名称。"}
        return {"status": "success", "message": f"IMAP 连接与登录成功，可读取配置的收件文件夹：{', '.join(folders)}。"}
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
    keywords = ("已完成", "完成") if notify_type == "task_done" else ("进行中", "处理中")
    reply_line = _find_explicit_reply_line(subject, strip_reply_guides(body), keywords)
    if not reply_line:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, notify_type, "FAILED", None, {"reason": "邮件开头未识别到明确状态回复指令"})
        return

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

    replied_recipient_id = _mark_notification_recipient_replied(
        db,
        task.id,
        sender.id,
        mail_event,
        TASK_REPLYABLE_NOTIFY_TYPES,
    )
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
            if next_status == "done":
                item.status = "done"
                updated_subtask_ids.append(item.id)
            elif item.status != "done":
                item.status = "in_progress"
                updated_subtask_ids.append(item.id)
        task.main_status = _derive_task_status_from_subtasks(
            db,
            task,
            db.query(TaskSubtask).filter(TaskSubtask.task_id == task.id).all(),
            current_user_id=sender.id,
            current_status=next_status,
        )
    else:
        # 未拆子任务时，仍沿用原有主任务状态回写逻辑。
        task.main_status = _derive_task_status_from_subtasks(
            db,
            task,
            db.query(TaskSubtask).filter(TaskSubtask.task_id == task.id).all(),
            current_user_id=sender.id,
            current_status=next_status,
        )
    if task.main_status == "done" and task.actual_minutes == 0:
        # 首次完成时补算实际耗时，避免后续重复覆盖人工修正数据。
        task.actual_minutes = max(int((shanghai_now_naive() - task.start_at).total_seconds() // 60), 0)
    if task.main_status == "done" and task.completed_at is None:
        task.completed_at = shanghai_now_naive()
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
            "replied_notification_recipient_id": replied_recipient_id,
        },
    )


def _apply_delay_request_from_mail(db: Session, mail_event: MailEvent, sender: User, subject: str, body: str) -> None:
    """根据成员邮件创建延期申请，并通知管理员审批。"""
    reply_line = _find_explicit_reply_line(subject, strip_reply_guides(body), ("延期",))
    if not reply_line:
        mail_event.process_status = "FAILED"
        _append_mail_action(db, mail_event.id, "delay_request", "FAILED", None, {"reason": "邮件开头未识别到明确延期回复指令"})
        return

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
    replied_recipient_id = _mark_notification_recipient_replied(
        db,
        task.id,
        sender.id,
        mail_event,
        TASK_REPLYABLE_NOTIFY_TYPES,
    )
    db.add(request_obj)
    db.flush()

    from app.services.notifications import create_notification_with_recipients

    admin_ids = [item.id for item in db.query(User).filter(User.role.in_(tuple(ADMIN_ROLES)), User.is_active.is_(True)).all()]
    extra_context = {
        "delay_request_id": request_obj.id,
        "applicant_name": sender.name,
        "proposed_deadline": proposed_deadline.strftime("%Y-%m-%d"),
        "apply_reason": body[:300],
    }
    create_notification_with_recipients(db, task.id, "email", "delay_approval", "", recipient_user_ids=admin_ids, extra_context=extra_context)
    create_notification_with_recipients(db, task.id, "qax", "delay_approval", "", recipient_user_ids=admin_ids, extra_context=extra_context)

    mail_event.process_status = "APPLIED"
    _append_mail_action(
        db,
        mail_event.id,
        "delay_request",
        "APPLIED",
        task.id,
        {
            "delay_request_id": request_obj.id,
            "proposed_deadline": proposed_deadline.strftime("%Y-%m-%d"),
            "replied_notification_recipient_id": replied_recipient_id,
        },
    )


def _parse_delay_approval(body: str, subject: str) -> tuple[str | None, datetime | None, str]:
    """从管理员邮件中解析同意/拒绝动作和审批日期。"""
    line = _find_explicit_reply_line(subject, body, ("同意", "拒绝"))
    if not line:
        return None, None, ""
    action = "APPROVE" if "同意" in line else "REJECT"
    approved_deadline = _parse_date(line)
    return action, approved_deadline, line


def _apply_delay_approval_from_mail(db: Session, mail_event: MailEvent, sender: User, subject: str, body: str) -> None:
    """根据管理员邮件执行延期审批。"""
    if sender.role not in ADMIN_ROLES:
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
        replied_recipient_id = _mark_notification_recipient_replied(
            db,
            request_obj.task_id,
            sender.id,
            mail_event,
            ("delay_approval",),
        )
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
        _append_mail_action(
            db,
            mail_event.id,
            "delay_approve",
            "APPLIED" if result in {"APPLIED", "IDEMPOTENT_REPLAY"} else "SKIPPED",
            updated.task_id,
            {
                "result": result,
                "delay_request_id": updated.id,
                "approval_status": updated.approval_status,
                "replied_notification_recipient_id": replied_recipient_id,
            },
        )
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
    elif template.notify_type in {"delay_request", "delay_approve"}:
        mail_event.process_status = "SKIPPED"
        _append_mail_action(
            db,
            mail_event.id,
            template.notify_type,
            "SKIPPED",
            None,
            {"reason": "延期审批流程已停用"},
        )
    else:
        mail_event.process_status = "MATCHED"
        _append_mail_action(db, mail_event.id, template.notify_type, "SKIPPED", None, {"reason": "模板类型暂不支持"})


def _poll_mailbox_via_imap(db: Session, state: MailScanState) -> dict[str, str | int]:
    """Scan unread messages from the configured IMAP folders."""
    if settings.imap_use_ssl and settings.imap_use_tls:
        return {"status": "failed", "message": "IMAP_USE_SSL 与 IMAP_USE_TLS 不能同时开启，请修正配置后重试。", "count": 0}

    folders = _mail_inbox_folder_names()
    with _open_imap_connection() as mailbox:
        mailbox.login(settings.imap_user, settings.imap_password)
        since_date = _imap_since_date(state.baseline_started_at)
        max_scan = load_runtime_settings().mail_inbox_max_scan
        templates = _mail_reply_templates(db)
        candidates: list[tuple[str, bytes, str, bytes, str]] = []
        candidate_message_ids: list[str] = []
        unread_total = 0
        scanned_total = 0
        failed_folders: list[str] = []

        for folder in folders:
            status, _ = mailbox.select(_imap_mailbox_arg(folder))
            if status != "OK":
                failed_folders.append(folder)
                continue
            if since_date:
                search_status, data = mailbox.search(None, "UNSEEN", "SINCE", since_date)
            else:
                search_status, data = mailbox.search(None, "UNSEEN")
            if search_status != "OK":
                failed_folders.append(folder)
                continue

            message_numbers = [item for item in data[0].split() if item]
            unread_total += len(message_numbers)
            if max_scan > 0:
                message_numbers = message_numbers[-max_scan:]
            scanned_total += len(message_numbers)

            for imap_id in message_numbers:
                header_status, header_data = mailbox.fetch(imap_id, f"({_MAIL_HEADER_FETCH})")
                if header_status != "OK":
                    continue
                header_message = _extract_imap_fetch_bytes(header_data)
                if not header_message:
                    continue
                fallback_prefix = _mailbox_fallback_prefix("imap", folder, _decode_imap_id(imap_id))
                header = email.message_from_bytes(header_message)
                if _is_message_before_baseline(header, state):
                    continue
                message_id = _resolve_message_id(header, header_message, fallback_prefix)
                candidates.append((folder, imap_id, fallback_prefix, header_message, message_id))
                candidate_message_ids.append(message_id)

        if failed_folders and len(failed_folders) == len(folders):
            return {"status": "failed", "message": f"IMAP 未能访问配置的收件文件夹：{', '.join(failed_folders)}。", "count": 0}

        existing_message_ids = _processed_mail_message_ids(db, candidate_message_ids)
        saved_count = 0
        for folder, imap_id, fallback_prefix, header_message, message_id in candidates:
            if message_id in existing_message_ids:
                continue
            mailbox.select(_imap_mailbox_arg(folder))
            body_status, body_data = mailbox.fetch(imap_id, f"(BODY.PEEK[TEXT]<0.{_MAIL_BODY_FETCH_BYTES}>)")
            if body_status != "OK":
                continue
            body_preview = _extract_imap_fetch_bytes(body_data)
            raw_message = _join_header_and_body_preview(header_message, body_preview)
            if _build_mail_event_from_message(
                db,
                state,
                raw_message,
                fallback_prefix,
                inbox_protocol="imap",
                inbox_folder=folder,
                server_message_ref=_decode_imap_id(imap_id),
                templates=templates,
                known_message_id=message_id,
                skip_existing_check=True,
                replace_unmatched_existing=True,
            ):
                saved_count += 1

        skipped_text = f"；跳过不可访问文件夹：{', '.join(failed_folders)}" if failed_folders else ""
        return {
            "status": "success",
            "message": f"本次通过 IMAP 扫描文件夹 {', '.join(folders)}，未读邮件 {scanned_total} 封（总未读 {unread_total} 封），已落库 {saved_count} 封{skipped_text}。",
            "count": saved_count,
        }


def _poll_mailbox_via_pop3(db: Session, state: MailScanState) -> dict[str, str | int]:
    """Scan recent messages via POP3, with optional folder selection when supported."""
    if settings.pop3_use_ssl and settings.pop3_use_tls:
        return {"status": "failed", "message": "POP3_USE_SSL 与 POP3_USE_TLS 不能同时开启，请修正配置后重试。", "count": 0}

    mail_server = _make_zmail_mail_server(settings.pop3_user, settings.pop3_password)
    folders = _mail_inbox_folder_names()
    selected_folder = folders[0]
    folder_fallback = False

    with _patched_mail_dns_resolution(), mail_server.pop_server as pop:
        for folder in folders:
            if _try_select_pop3_folder(pop, folder):
                selected_folder = folder
                break
        else:
            selected_folder = "INBOX"
            folder_fallback = True

        _, listings, _ = pop.server.list()
        message_numbers = [int(line.split()[0]) for line in listings if line]
        total_count = len(message_numbers)
        max_scan = load_runtime_settings().mail_inbox_max_scan
        if max_scan > 0:
            message_numbers = message_numbers[-max_scan:]

        templates = _mail_reply_templates(db)
        candidates: list[tuple[int, bytes, str, str]] = []
        candidate_message_ids: list[str] = []
        for message_number in message_numbers:
            header_lines = _pop3_top(pop, message_number, 0)
            header_message = b"\r\n".join(header_lines)
            fallback_prefix = _mailbox_fallback_prefix("pop3", selected_folder, message_number)
            header = email.message_from_bytes(header_message)
            if _is_message_before_baseline(header, state):
                continue
            if not _is_system_mail_subject(_decode_header_value(header.get("Subject"))):
                continue
            message_id = _resolve_message_id(header, header_message, fallback_prefix)
            candidates.append((message_number, header_message, fallback_prefix, message_id))
            candidate_message_ids.append(message_id)

        existing_message_ids = _processed_mail_message_ids(db, candidate_message_ids)
        saved_count = 0
        for message_number, header_message, fallback_prefix, message_id in candidates:
            if message_id in existing_message_ids:
                continue
            body_lines = _pop3_top(pop, message_number, _POP3_BODY_PREVIEW_LINES)
            raw_message = b"\r\n".join(body_lines)
            if _build_mail_event_from_message(
                db,
                state,
                raw_message,
                fallback_prefix,
                inbox_protocol="pop3",
                inbox_folder=selected_folder,
                server_message_ref=str(message_number),
                templates=templates,
                known_message_id=message_id,
                skip_existing_check=True,
                replace_unmatched_existing=True,
            ):
                saved_count += 1

        fallback_text = "；POP3 服务未暴露文件夹选择能力，已兼容扫描默认邮箱列表" if folder_fallback else ""
        return {
            "status": "success",
            "message": f"本次通过 POP3 扫描文件夹 {selected_folder} 最近邮件 {len(message_numbers)} 封（总邮件 {total_count} 封），已落库 {saved_count} 封{fallback_text}。",
            "count": saved_count,
        }


def poll_mailbox(db: Session) -> dict[str, str | int]:
    """扫描邮箱未读邮件并写入系统。

    说明:
    - 首次运行只建立基线，不处理历史邮件；
    - 仅扫描未读邮件，并限制单次最大扫描数量；
    - 邮件成功匹配回复模板后会尝试触发对应业务动作。
    """
    with _mail_poll_guard() as acquired:
        if not acquired:
            return {
                "status": "busy",
                "message": "另一项邮件收取任务正在执行，请稍后重试。",
                "count": 0,
            }

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
                cleanup_result = cleanup_applied_task_reply_mails(db)
                state.last_scan_at = shanghai_now_naive()
                if cleanup_result.get("deleted_count") or cleanup_result.get("failed_count"):
                    result = {
                        **result,
                        "deleted_mail_count": int(cleanup_result.get("deleted_count") or 0),
                        "delete_failed_count": int(cleanup_result.get("failed_count") or 0),
                        "delete_result": cleanup_result,
                        "message": (
                            f"{result.get('message', '')} 已清理匹配邮件 {cleanup_result.get('deleted_count', 0)} 封"
                            f"；删除失败 {cleanup_result.get('failed_count', 0)} 封。"
                        ),
                    }
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
            return {"status": "failed", "message": _pop3_protocol_error_hint(exc), "count": 0}
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

    # 使用 zmail 统一构造与发送，保持现有参数和返回结构不变。
    mail_dict = {
        "subject": _format_system_mail_subject(subject),
        "content_text": content,
        "content_html": _plain_text_to_html(content),
        "from": settings.smtp_from_address,
        "headers": {"To": to_address},
    }
    message = ZmailMime(mail_dict)

    try:
        with _open_smtp_connection() as server:
            server.send([to_address], message, settings.smtp_timeout_seconds)
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
