from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import base_settings, settings
from app.timeutils import shanghai_now_naive


APP_RUNTIME_SETTINGS_KEY = "runtime_settings"


@dataclass
class RuntimeSettings:
    mail_auto_poll_enabled: bool = base_settings.mail_auto_poll_enabled
    mail_auto_poll_interval_seconds: int = base_settings.mail_auto_poll_interval_seconds
    mail_inbox_max_scan: int = base_settings.mail_inbox_max_scan
    due_remind_enabled: bool = True
    due_remind_run_at: str = base_settings.remind_daily_run_at
    overdue_remind_enabled: bool = True
    overdue_remind_run_at: str = "09:00"
    completed_mail_cleanup_enabled: bool = True
    completed_mail_cleanup_retention_days: int = 30
    system_log_cleanup_enabled: bool = True
    system_log_retention_days: int = base_settings.system_log_retention_days
    system_log_cleanup_interval_seconds: int = base_settings.system_log_cleanup_interval_seconds
    qax_auto_collect_enabled: bool = bool((base_settings.qax_collect_cron or "").strip())
    qax_auto_collect_interval_seconds: int = 3600
    mail_scan_baseline_at: str = ""
    qax_browser_visible: bool = not base_settings.qax_browser_headless
    qax_base_url: str = base_settings.qax_base_url
    qax_username: str = base_settings.qax_username
    qax_password: str = base_settings.qax_password
    qax_group_name: str = base_settings.qax_group_name
    qax_ignore_https_errors: bool = base_settings.qax_ignore_https_errors
    smtp_host: str = base_settings.smtp_host
    smtp_port: int = base_settings.smtp_port
    smtp_user: str = base_settings.smtp_user
    smtp_password: str = base_settings.smtp_password
    smtp_from_address: str = base_settings.smtp_from_address
    smtp_use_tls: bool = base_settings.smtp_use_tls
    smtp_use_ssl: bool = base_settings.smtp_use_ssl
    smtp_timeout_seconds: int = base_settings.smtp_timeout_seconds
    mail_inbox_protocol: str = base_settings.mail_inbox_protocol
    imap_host: str = base_settings.imap_host
    imap_port: int = base_settings.imap_port
    imap_user: str = base_settings.imap_user
    imap_password: str = base_settings.imap_password
    imap_use_tls: bool = base_settings.imap_use_tls
    imap_use_ssl: bool = base_settings.imap_use_ssl
    pop3_host: str = base_settings.pop3_host
    pop3_port: int = base_settings.pop3_port
    pop3_user: str = base_settings.pop3_user
    pop3_password: str = base_settings.pop3_password
    pop3_use_tls: bool = base_settings.pop3_use_tls
    pop3_use_ssl: bool = base_settings.pop3_use_ssl
    mail_inbox_folders: str = base_settings.mail_inbox_folders
    dns_auto_resolve_enabled: bool = True
    mail_host_mappings: list[dict[str, Any]] = field(default_factory=list)


BOOL_FIELDS = {
    "mail_auto_poll_enabled",
    "due_remind_enabled",
    "overdue_remind_enabled",
    "completed_mail_cleanup_enabled",
    "system_log_cleanup_enabled",
    "qax_auto_collect_enabled",
    "qax_browser_visible",
    "qax_ignore_https_errors",
    "smtp_use_tls",
    "smtp_use_ssl",
    "imap_use_tls",
    "imap_use_ssl",
    "pop3_use_tls",
    "pop3_use_ssl",
    "dns_auto_resolve_enabled",
}
INT_FIELDS = {
    "mail_auto_poll_interval_seconds",
    "mail_inbox_max_scan",
    "completed_mail_cleanup_retention_days",
    "system_log_retention_days",
    "system_log_cleanup_interval_seconds",
    "qax_auto_collect_interval_seconds",
    "smtp_port",
    "smtp_timeout_seconds",
    "imap_port",
    "pop3_port",
}
TIME_FIELDS = {"due_remind_run_at", "overdue_remind_run_at"}


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _coerce_int(value: Any, default: int, minimum: int) -> int:
    try:
        return max(int(value), minimum)
    except (TypeError, ValueError):
        return max(default, minimum)


def _coerce_time(value: Any, default: str) -> str:
    text = str(value or default or "09:00").strip()
    try:
        parsed = datetime.strptime(text, "%H:%M")
    except ValueError:
        return default or "09:00"
    return parsed.strftime("%H:%M")


def _coerce_text(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value).strip()


def _coerce_protocol(value: Any, default: str) -> str:
    text = str(value or default or "imap").strip().lower()
    return text if text in {"imap", "pop3"} else (default if default in {"imap", "pop3"} else "imap")


def _open_session_if_needed(db: Session | None) -> tuple[Session, bool]:
    if db is not None:
        return db, False
    from app.db import SessionLocal

    return SessionLocal(), True


def _load_settings_json(db: Session) -> dict[str, Any]:
    from app.models import AppSetting

    record = db.get(AppSetting, APP_RUNTIME_SETTINGS_KEY)
    if not record:
        return {}
    try:
        raw = json.loads(record.value_json or "{}")
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _host_mapping_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "host": row.host,
        "ip": row.ip,
        "enabled": row.enabled,
        "source": row.source,
        "note": row.note,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else "",
    }


def _load_host_mappings(db: Session) -> list[dict[str, Any]]:
    from app.models import HostIpMapping

    rows = db.query(HostIpMapping).order_by(HostIpMapping.host.asc()).all()
    return [_host_mapping_dict(row) for row in rows]


def _apply_raw_settings(current: RuntimeSettings, raw: dict[str, Any]) -> RuntimeSettings:
    for field_name in current.__dataclass_fields__:
        if field_name == "mail_host_mappings" or field_name not in raw:
            continue
        default = getattr(current, field_name)
        if field_name in BOOL_FIELDS:
            setattr(current, field_name, _coerce_bool(raw.get(field_name), default))
        elif field_name in INT_FIELDS:
            minimum = 300 if field_name == "system_log_cleanup_interval_seconds" else 30 if field_name in {"mail_auto_poll_interval_seconds", "qax_auto_collect_interval_seconds"} else 1
            setattr(current, field_name, _coerce_int(raw.get(field_name), default, minimum))
        elif field_name in TIME_FIELDS:
            setattr(current, field_name, _coerce_time(raw.get(field_name), default))
        elif field_name == "mail_inbox_protocol":
            setattr(current, field_name, _coerce_protocol(raw.get(field_name), default))
        else:
            setattr(current, field_name, _coerce_text(raw.get(field_name), default))
    return current


def _apply_session_overrides(current: RuntimeSettings) -> None:
    for field_name in current.__dataclass_fields__:
        if field_name == "mail_host_mappings":
            continue
        override = getattr(settings, "get_session_override")(field_name)
        if override is None:
            continue
        _apply_raw_settings(current, {field_name: override})


def load_runtime_settings(db: Session | None = None) -> RuntimeSettings:
    session, should_close = _open_session_if_needed(db)
    try:
        current = _apply_raw_settings(RuntimeSettings(), _load_settings_json(session))
        current.mail_host_mappings = _load_host_mappings(session)
        _apply_session_overrides(current)
        return current
    finally:
        if should_close:
            session.close()


def _normalize_host(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"//{text}")
    return (parsed.hostname or text).strip().lower()


def _resolve_host(host: str, port: int | None = None) -> str:
    if not host:
        return ""
    try:
        socket.inet_aton(host)
        return host
    except OSError:
        pass
    try:
        infos = socket.getaddrinfo(host, port or 0, proto=socket.IPPROTO_TCP)
    except OSError:
        return ""
    for info in infos:
        ip = str(info[4][0]).strip()
        if ip and ":" not in ip:
            return ip
    return str(infos[0][4][0]).strip() if infos else ""


def _upsert_host_mapping(db: Session, host: str, ip: str, *, enabled: bool = True, source: str = "manual", note: str = "") -> None:
    from app.models import HostIpMapping

    normalized_host = _normalize_host(host)
    if not normalized_host:
        return
    row = db.query(HostIpMapping).filter(HostIpMapping.host == normalized_host).one_or_none()
    if row is None:
        row = HostIpMapping(host=normalized_host)
        db.add(row)
    row.ip = str(ip or "").strip()
    row.enabled = bool(enabled)
    row.source = source or "manual"
    row.note = str(note or "").strip()
    row.resolved_at = shanghai_now_naive() if row.ip and row.source == "dns" else row.resolved_at


def _save_host_mappings(db: Session, mappings: Any) -> None:
    if not isinstance(mappings, list):
        return
    from app.models import HostIpMapping

    seen_hosts: set[str] = set()
    for item in mappings:
        if not isinstance(item, dict):
            continue
        host = _normalize_host(item.get("host"))
        if host:
            seen_hosts.add(host)
        _upsert_host_mapping(
            db,
            host,
            item.get("ip"),
            enabled=_coerce_bool(item.get("enabled"), True),
            source=_coerce_text(item.get("source"), "manual") or "manual",
            note=_coerce_text(item.get("note"), ""),
        )
    for row in db.query(HostIpMapping).all():
        if row.host not in seen_hosts and row.source != "dns":
            db.delete(row)


def _auto_resolve_configured_hosts(db: Session, data: dict[str, Any]) -> None:
    if not _coerce_bool(data.get("dns_auto_resolve_enabled"), True):
        return
    candidates = [
        (data.get("smtp_host"), _coerce_int(data.get("smtp_port"), 25, 1)),
        (data.get("imap_host"), _coerce_int(data.get("imap_port"), 993, 1)),
        (data.get("pop3_host"), _coerce_int(data.get("pop3_port"), 110, 1)),
    ]
    qax_host = _normalize_host(data.get("qax_base_url"))
    if qax_host:
        candidates.append((qax_host, None))
    for item in data.get("mail_host_mappings") or []:
        if isinstance(item, dict) and item.get("host") and not item.get("ip"):
            candidates.append((item.get("host"), None))
    for host, port in candidates:
        normalized_host = _normalize_host(host)
        if not normalized_host:
            continue
        ip = _resolve_host(normalized_host, port)
        if ip:
            _upsert_host_mapping(db, normalized_host, ip, enabled=True, source="dns")


def save_runtime_settings(values: dict[str, Any], db: Session | None = None) -> RuntimeSettings:
    session, should_close = _open_session_if_needed(db)
    try:
        current = load_runtime_settings(session)
        data = asdict(current)
        data.update(values)
        if data.get("mail_scan_baseline_at"):
            datetime.fromisoformat(str(data["mail_scan_baseline_at"]).replace("Z", "+00:00"))
        updated = asdict(_apply_raw_settings(RuntimeSettings(), data))
        updated["mail_scan_baseline_at"] = str(data.get("mail_scan_baseline_at") or "").strip()
        updated["mail_host_mappings"] = data.get("mail_host_mappings") or []

        from app.models import AppSetting

        record = session.get(AppSetting, APP_RUNTIME_SETTINGS_KEY)
        if record is None:
            record = AppSetting(key=APP_RUNTIME_SETTINGS_KEY)
            session.add(record)
        record.value_json = json.dumps({k: v for k, v in updated.items() if k != "mail_host_mappings"}, ensure_ascii=False)
        _save_host_mappings(session, updated["mail_host_mappings"])
        _auto_resolve_configured_hosts(session, updated)
        if should_close:
            session.commit()
        else:
            session.flush()
        return load_runtime_settings(session)
    finally:
        if should_close:
            session.close()


def load_host_ip_mappings(db: Session | None = None) -> dict[str, str]:
    session, should_close = _open_session_if_needed(db)
    try:
        from app.models import HostIpMapping

        rows = db.query(HostIpMapping).filter(HostIpMapping.enabled.is_(True)).all() if db is not None else session.query(HostIpMapping).filter(HostIpMapping.enabled.is_(True)).all()
        return {row.host.lower(): row.ip for row in rows if row.host and row.ip}
    finally:
        if should_close:
            session.close()


def runtime_settings_dict(db: Session | None = None) -> dict[str, Any]:
    return asdict(load_runtime_settings(db))
