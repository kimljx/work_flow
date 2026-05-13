from __future__ import annotations

"""Application configuration loading and runtime overrides."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_OVERRIDE_PATH = PROJECT_ROOT / "config" / "runtime-settings.json"


def _load_env_file(path: Path) -> None:
    """Load missing environment variables from a local .env file."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_load_env_file(PROJECT_ROOT / ".env")


@dataclass
class Settings:
    app_name: str
    app_env: str
    secret_key: str
    access_token_expire_minutes: int
    refresh_token_expire_minutes: int
    database_url: str
    default_password: str
    qax_collect_cron: str
    qax_base_url: str
    qax_username: str
    qax_password: str
    qax_group_name: str
    qax_browser_headless: bool
    qax_ignore_https_errors: bool
    remind_daily_run_at: str
    system_log_retention_days: int
    system_log_cleanup_interval_seconds: int
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from_address: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    smtp_timeout_seconds: int
    mail_inbox_protocol: str
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_use_tls: bool
    imap_use_ssl: bool
    pop3_host: str
    pop3_port: int
    pop3_user: str
    pop3_password: str
    pop3_use_tls: bool
    pop3_use_ssl: bool
    mail_inbox_max_scan: int
    imap_max_unseen_scan: int
    mail_auto_poll_enabled: bool
    mail_auto_poll_interval_seconds: int


base_settings = Settings(
    app_name=os.getenv("APP_NAME", "部门任务协同系统"),
    app_env=os.getenv("APP_ENV", "dev"),
    secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
    access_token_expire_minutes=_as_int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"), 60),
    refresh_token_expire_minutes=_as_int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"), 10080),
    database_url=os.getenv("DATABASE_URL", "sqlite:///./backend/data/app.db"),
    default_password=os.getenv("DEFAULT_PASSWORD", "ChangeMe123"),
    qax_collect_cron=os.getenv("QAX_COLLECT_CRON", "0 * * * *"),
    qax_base_url=os.getenv("QAX_BASE_URL", "").strip(),
    qax_username=os.getenv("QAX_USERNAME", "").strip(),
    qax_password=os.getenv("QAX_PASSWORD", "").strip(),
    qax_group_name=os.getenv("QAX_GROUP_NAME", "普通分组").strip() or "普通分组",
    qax_browser_headless=_as_bool(os.getenv("QAX_BROWSER_HEADLESS", "true"), True),
    qax_ignore_https_errors=_as_bool(os.getenv("QAX_IGNORE_HTTPS_ERRORS", "true"), True),
    remind_daily_run_at=os.getenv("REMIND_DAILY_RUN_AT", "09:00").strip() or "09:00",
    system_log_retention_days=max(_as_int(os.getenv("SYSTEM_LOG_RETENTION_DAYS", "60"), 60), 1),
    system_log_cleanup_interval_seconds=max(_as_int(os.getenv("SYSTEM_LOG_CLEANUP_INTERVAL_SECONDS", "86400"), 86400), 300),
    smtp_host=os.getenv("SMTP_HOST", "").strip(),
    smtp_port=_as_int(os.getenv("SMTP_PORT", "25"), 25),
    smtp_user=os.getenv("SMTP_USER", "").strip(),
    smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
    smtp_from_address=os.getenv("SMTP_FROM_ADDRESS", "").strip(),
    smtp_use_tls=_as_bool(os.getenv("SMTP_USE_TLS", "false"), False),
    smtp_use_ssl=_as_bool(os.getenv("SMTP_USE_SSL", "false"), False),
    smtp_timeout_seconds=_as_int(os.getenv("SMTP_TIMEOUT_SECONDS", "20"), 20),
    mail_inbox_protocol=os.getenv("MAIL_INBOX_PROTOCOL", "imap").strip().lower() or "imap",
    imap_host=os.getenv("IMAP_HOST", "").strip(),
    imap_port=_as_int(os.getenv("IMAP_PORT", "993"), 993),
    imap_user=os.getenv("IMAP_USER", "").strip(),
    imap_password=os.getenv("IMAP_PASSWORD", "").strip(),
    imap_use_tls=_as_bool(os.getenv("IMAP_USE_TLS", "false"), False),
    imap_use_ssl=_as_bool(os.getenv("IMAP_USE_SSL", "true"), True),
    pop3_host=os.getenv("POP3_HOST", "").strip(),
    pop3_port=_as_int(os.getenv("POP3_PORT", "110"), 110),
    pop3_user=os.getenv("POP3_USER", "").strip(),
    pop3_password=os.getenv("POP3_PASSWORD", "").strip(),
    pop3_use_tls=_as_bool(os.getenv("POP3_USE_TLS", "false"), False),
    pop3_use_ssl=_as_bool(os.getenv("POP3_USE_SSL", "false"), False),
    mail_inbox_max_scan=_as_int(os.getenv("MAIL_INBOX_MAX_SCAN", os.getenv("IMAP_MAX_UNSEEN_SCAN", "20")), 20),
    imap_max_unseen_scan=_as_int(os.getenv("IMAP_MAX_UNSEEN_SCAN", "20"), 20),
    mail_auto_poll_enabled=_as_bool(os.getenv("MAIL_AUTO_POLL_ENABLED", "true"), True),
    mail_auto_poll_interval_seconds=_as_int(os.getenv("MAIL_AUTO_POLL_INTERVAL_SECONDS", "300"), 300),
)


EDITABLE_SETTING_FIELDS = {
    "qax_base_url",
    "qax_username",
    "qax_password",
    "qax_group_name",
    "qax_ignore_https_errors",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "smtp_from_address",
    "smtp_use_tls",
    "smtp_use_ssl",
    "smtp_timeout_seconds",
    "mail_inbox_protocol",
    "imap_host",
    "imap_port",
    "imap_user",
    "imap_password",
    "imap_use_tls",
    "imap_use_ssl",
    "pop3_host",
    "pop3_port",
    "pop3_user",
    "pop3_password",
    "pop3_use_tls",
    "pop3_use_ssl",
    "mail_inbox_max_scan",
    "mail_auto_poll_enabled",
    "mail_auto_poll_interval_seconds",
}

INT_SETTING_FIELDS = {
    "smtp_port",
    "smtp_timeout_seconds",
    "imap_port",
    "pop3_port",
    "mail_inbox_max_scan",
    "mail_auto_poll_interval_seconds",
}

BOOL_SETTING_FIELDS = {
    "qax_ignore_https_errors",
    "smtp_use_tls",
    "smtp_use_ssl",
    "imap_use_tls",
    "imap_use_ssl",
    "pop3_use_tls",
    "pop3_use_ssl",
    "mail_auto_poll_enabled",
}


def _read_runtime_overrides() -> dict[str, Any]:
    if not RUNTIME_OVERRIDE_PATH.exists():
        return {}
    try:
        raw = json.loads(RUNTIME_OVERRIDE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_override(name: str, value: Any, default: Any) -> Any:
    if name == "mail_inbox_protocol":
        text = str(value or default or "imap").strip().lower()
        return text if text in {"imap", "pop3"} else (default if default in {"imap", "pop3"} else "imap")
    if name in BOOL_SETTING_FIELDS:
        return _as_bool(value, bool(default))
    if name in INT_SETTING_FIELDS:
        return _as_int(value, int(default))
    return str(value or "").strip() if isinstance(default, str) else value


class SettingsProxy:
    """Expose base settings with runtime overrides for editable fields."""

    def __init__(self, base: Settings) -> None:
        object.__setattr__(self, "_base", base)
        object.__setattr__(self, "_session_overrides", {})

    def __getattr__(self, name: str) -> Any:
        if not hasattr(self._base, name):
            raise AttributeError(name)
        if name in self._session_overrides:
            return self._session_overrides[name]
        default = getattr(self._base, name)
        overrides = _read_runtime_overrides()
        if name == "qax_browser_headless" and "qax_browser_visible" in overrides:
            return not _as_bool(overrides.get("qax_browser_visible"), not bool(default))
        if name in EDITABLE_SETTING_FIELDS and name in overrides:
            return _coerce_override(name, overrides.get(name), default)
        return default

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_base", "_session_overrides"}:
            object.__setattr__(self, name, value)
            return
        if hasattr(self._base, name):
            self._session_overrides[name] = value
            setattr(self._base, name, value)
            return
        object.__setattr__(self, name, value)

    def get_session_override(self, name: str) -> Any:
        return self._session_overrides.get(name)


settings = SettingsProxy(base_settings)
