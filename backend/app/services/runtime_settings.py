from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, base_settings, settings


RUNTIME_SETTINGS_PATH = PROJECT_ROOT / "config" / "runtime-settings.json"


@dataclass
class RuntimeSettings:
    mail_auto_poll_enabled: bool = base_settings.mail_auto_poll_enabled
    mail_auto_poll_interval_seconds: int = base_settings.mail_auto_poll_interval_seconds
    mail_inbox_max_scan: int = base_settings.mail_inbox_max_scan
    due_remind_enabled: bool = True
    due_remind_run_at: str = base_settings.remind_daily_run_at
    overdue_remind_enabled: bool = True
    overdue_remind_run_at: str = "09:00"
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


def _default_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings()


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


def load_runtime_settings() -> RuntimeSettings:
    current = _default_runtime_settings()
    if not RUNTIME_SETTINGS_PATH.exists():
        return current
    try:
        raw = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return current

    current.mail_auto_poll_enabled = _coerce_bool(raw.get("mail_auto_poll_enabled"), current.mail_auto_poll_enabled)
    current.mail_auto_poll_interval_seconds = _coerce_int(raw.get("mail_auto_poll_interval_seconds"), current.mail_auto_poll_interval_seconds, 30)
    current.mail_inbox_max_scan = _coerce_int(raw.get("mail_inbox_max_scan"), current.mail_inbox_max_scan, 1)
    current.due_remind_enabled = _coerce_bool(raw.get("due_remind_enabled"), current.due_remind_enabled)
    current.due_remind_run_at = _coerce_time(raw.get("due_remind_run_at"), current.due_remind_run_at)
    current.overdue_remind_enabled = _coerce_bool(raw.get("overdue_remind_enabled"), current.overdue_remind_enabled)
    current.overdue_remind_run_at = _coerce_time(raw.get("overdue_remind_run_at"), current.overdue_remind_run_at)
    current.qax_auto_collect_enabled = _coerce_bool(raw.get("qax_auto_collect_enabled"), current.qax_auto_collect_enabled)
    current.qax_auto_collect_interval_seconds = _coerce_int(raw.get("qax_auto_collect_interval_seconds"), current.qax_auto_collect_interval_seconds, 30)
    current.mail_scan_baseline_at = str(raw.get("mail_scan_baseline_at") or "").strip()
    current.qax_browser_visible = _coerce_bool(raw.get("qax_browser_visible"), current.qax_browser_visible)
    current.qax_base_url = _coerce_text(raw.get("qax_base_url"), current.qax_base_url)
    current.qax_username = _coerce_text(raw.get("qax_username"), current.qax_username)
    current.qax_password = _coerce_text(raw.get("qax_password"), current.qax_password)
    current.qax_group_name = _coerce_text(raw.get("qax_group_name"), current.qax_group_name)
    current.qax_ignore_https_errors = _coerce_bool(raw.get("qax_ignore_https_errors"), current.qax_ignore_https_errors)
    current.smtp_host = _coerce_text(raw.get("smtp_host"), current.smtp_host)
    current.smtp_port = _coerce_int(raw.get("smtp_port"), current.smtp_port, 1)
    current.smtp_user = _coerce_text(raw.get("smtp_user"), current.smtp_user)
    current.smtp_password = _coerce_text(raw.get("smtp_password"), current.smtp_password)
    current.smtp_from_address = _coerce_text(raw.get("smtp_from_address"), current.smtp_from_address)
    current.smtp_use_tls = _coerce_bool(raw.get("smtp_use_tls"), current.smtp_use_tls)
    current.smtp_use_ssl = _coerce_bool(raw.get("smtp_use_ssl"), current.smtp_use_ssl)
    current.smtp_timeout_seconds = _coerce_int(raw.get("smtp_timeout_seconds"), current.smtp_timeout_seconds, 1)
    current.mail_inbox_protocol = _coerce_protocol(raw.get("mail_inbox_protocol"), current.mail_inbox_protocol)
    current.imap_host = _coerce_text(raw.get("imap_host"), current.imap_host)
    current.imap_port = _coerce_int(raw.get("imap_port"), current.imap_port, 1)
    current.imap_user = _coerce_text(raw.get("imap_user"), current.imap_user)
    current.imap_password = _coerce_text(raw.get("imap_password"), current.imap_password)
    current.imap_use_tls = _coerce_bool(raw.get("imap_use_tls"), current.imap_use_tls)
    current.imap_use_ssl = _coerce_bool(raw.get("imap_use_ssl"), current.imap_use_ssl)
    current.pop3_host = _coerce_text(raw.get("pop3_host"), current.pop3_host)
    current.pop3_port = _coerce_int(raw.get("pop3_port"), current.pop3_port, 1)
    current.pop3_user = _coerce_text(raw.get("pop3_user"), current.pop3_user)
    current.pop3_password = _coerce_text(raw.get("pop3_password"), current.pop3_password)
    current.pop3_use_tls = _coerce_bool(raw.get("pop3_use_tls"), current.pop3_use_tls)
    current.pop3_use_ssl = _coerce_bool(raw.get("pop3_use_ssl"), current.pop3_use_ssl)
    _apply_session_overrides(current)
    return current


def _apply_session_overrides(current: RuntimeSettings) -> None:
    for field_name in current.__dataclass_fields__:
        override = getattr(settings, "get_session_override")(field_name)
        if override is None:
            continue
        if field_name in {"mail_auto_poll_enabled", "due_remind_enabled", "overdue_remind_enabled", "qax_auto_collect_enabled", "qax_browser_visible", "qax_ignore_https_errors", "smtp_use_tls", "smtp_use_ssl", "imap_use_tls", "imap_use_ssl", "pop3_use_tls", "pop3_use_ssl"}:
            setattr(current, field_name, _coerce_bool(override, getattr(current, field_name)))
        elif field_name in {"mail_auto_poll_interval_seconds", "mail_inbox_max_scan", "qax_auto_collect_interval_seconds", "smtp_port", "smtp_timeout_seconds", "imap_port", "pop3_port"}:
            setattr(current, field_name, _coerce_int(override, getattr(current, field_name), 1))
        elif field_name in {"due_remind_run_at", "overdue_remind_run_at"}:
            setattr(current, field_name, _coerce_time(override, getattr(current, field_name)))
        elif field_name == "mail_inbox_protocol":
            setattr(current, field_name, _coerce_protocol(override, getattr(current, field_name)))
        else:
            setattr(current, field_name, _coerce_text(override, getattr(current, field_name)))


def save_runtime_settings(values: dict[str, Any]) -> RuntimeSettings:
    current = load_runtime_settings()
    data = asdict(current)
    data.update(values)
    if data.get("mail_scan_baseline_at"):
        datetime.fromisoformat(str(data["mail_scan_baseline_at"]).replace("Z", "+00:00"))
    updated = RuntimeSettings(
        mail_auto_poll_enabled=_coerce_bool(data.get("mail_auto_poll_enabled"), current.mail_auto_poll_enabled),
        mail_auto_poll_interval_seconds=_coerce_int(data.get("mail_auto_poll_interval_seconds"), current.mail_auto_poll_interval_seconds, 30),
        mail_inbox_max_scan=_coerce_int(data.get("mail_inbox_max_scan"), current.mail_inbox_max_scan, 1),
        due_remind_enabled=_coerce_bool(data.get("due_remind_enabled"), current.due_remind_enabled),
        due_remind_run_at=_coerce_time(data.get("due_remind_run_at"), current.due_remind_run_at),
        overdue_remind_enabled=_coerce_bool(data.get("overdue_remind_enabled"), current.overdue_remind_enabled),
        overdue_remind_run_at=_coerce_time(data.get("overdue_remind_run_at"), current.overdue_remind_run_at),
        qax_auto_collect_enabled=_coerce_bool(data.get("qax_auto_collect_enabled"), current.qax_auto_collect_enabled),
        qax_auto_collect_interval_seconds=_coerce_int(data.get("qax_auto_collect_interval_seconds"), current.qax_auto_collect_interval_seconds, 30),
        mail_scan_baseline_at=str(data.get("mail_scan_baseline_at") or "").strip(),
        qax_browser_visible=_coerce_bool(data.get("qax_browser_visible"), current.qax_browser_visible),
        qax_base_url=_coerce_text(data.get("qax_base_url"), current.qax_base_url),
        qax_username=_coerce_text(data.get("qax_username"), current.qax_username),
        qax_password=_coerce_text(data.get("qax_password"), current.qax_password),
        qax_group_name=_coerce_text(data.get("qax_group_name"), current.qax_group_name),
        qax_ignore_https_errors=_coerce_bool(data.get("qax_ignore_https_errors"), current.qax_ignore_https_errors),
        smtp_host=_coerce_text(data.get("smtp_host"), current.smtp_host),
        smtp_port=_coerce_int(data.get("smtp_port"), current.smtp_port, 1),
        smtp_user=_coerce_text(data.get("smtp_user"), current.smtp_user),
        smtp_password=_coerce_text(data.get("smtp_password"), current.smtp_password),
        smtp_from_address=_coerce_text(data.get("smtp_from_address"), current.smtp_from_address),
        smtp_use_tls=_coerce_bool(data.get("smtp_use_tls"), current.smtp_use_tls),
        smtp_use_ssl=_coerce_bool(data.get("smtp_use_ssl"), current.smtp_use_ssl),
        smtp_timeout_seconds=_coerce_int(data.get("smtp_timeout_seconds"), current.smtp_timeout_seconds, 1),
        mail_inbox_protocol=_coerce_protocol(data.get("mail_inbox_protocol"), current.mail_inbox_protocol),
        imap_host=_coerce_text(data.get("imap_host"), current.imap_host),
        imap_port=_coerce_int(data.get("imap_port"), current.imap_port, 1),
        imap_user=_coerce_text(data.get("imap_user"), current.imap_user),
        imap_password=_coerce_text(data.get("imap_password"), current.imap_password),
        imap_use_tls=_coerce_bool(data.get("imap_use_tls"), current.imap_use_tls),
        imap_use_ssl=_coerce_bool(data.get("imap_use_ssl"), current.imap_use_ssl),
        pop3_host=_coerce_text(data.get("pop3_host"), current.pop3_host),
        pop3_port=_coerce_int(data.get("pop3_port"), current.pop3_port, 1),
        pop3_user=_coerce_text(data.get("pop3_user"), current.pop3_user),
        pop3_password=_coerce_text(data.get("pop3_password"), current.pop3_password),
        pop3_use_tls=_coerce_bool(data.get("pop3_use_tls"), current.pop3_use_tls),
        pop3_use_ssl=_coerce_bool(data.get("pop3_use_ssl"), current.pop3_use_ssl),
    )
    RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_SETTINGS_PATH.write_text(json.dumps(asdict(updated), ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


def runtime_settings_dict() -> dict[str, Any]:
    return asdict(load_runtime_settings())
