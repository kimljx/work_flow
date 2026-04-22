from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
    remind_daily_run_at: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from_address: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    smtp_timeout_seconds: int
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_max_unseen_scan: int
    mail_auto_poll_enabled: bool
    mail_auto_poll_interval_seconds: int


settings = Settings(
    app_name=os.getenv("APP_NAME", "工作流管理系统"),
    app_env=os.getenv("APP_ENV", "dev"),
    secret_key=os.getenv("SECRET_KEY", "change-me-in-production"),
    access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
    refresh_token_expire_minutes=int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080")),
    database_url=os.getenv("DATABASE_URL", "sqlite:///./backend/data/app.db"),
    default_password=os.getenv("DEFAULT_PASSWORD", "ChangeMe123"),
    qax_collect_cron=os.getenv("QAX_COLLECT_CRON", "0 * * * *"),
    remind_daily_run_at=os.getenv("REMIND_DAILY_RUN_AT", "09:00"),
    smtp_host=os.getenv("SMTP_HOST", ""),
    smtp_port=int(os.getenv("SMTP_PORT", "25")),
    smtp_user=os.getenv("SMTP_USER", ""),
    smtp_password=os.getenv("SMTP_PASSWORD", ""),
    smtp_from_address=os.getenv("SMTP_FROM_ADDRESS", ""),
    smtp_use_tls=os.getenv("SMTP_USE_TLS", "false").lower() == "true",
    smtp_use_ssl=os.getenv("SMTP_USE_SSL", "false").lower() == "true",
    smtp_timeout_seconds=int(os.getenv("SMTP_TIMEOUT_SECONDS", "20")),
    imap_host=os.getenv("IMAP_HOST", ""),
    imap_port=int(os.getenv("IMAP_PORT", "993")),
    imap_user=os.getenv("IMAP_USER", ""),
    imap_password=os.getenv("IMAP_PASSWORD", ""),
    imap_max_unseen_scan=int(os.getenv("IMAP_MAX_UNSEEN_SCAN", "20")),
    mail_auto_poll_enabled=os.getenv("MAIL_AUTO_POLL_ENABLED", "true").lower() == "true",
    mail_auto_poll_interval_seconds=int(os.getenv("MAIL_AUTO_POLL_INTERVAL_SECONDS", "300")),
)
