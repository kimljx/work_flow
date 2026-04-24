from __future__ import annotations

"""应用配置加载模块。

统一负责读取 `.env` 与系统环境变量，并转换为强类型配置对象，
供后端所有模块复用，避免在业务代码中直接散落读取环境变量。
"""

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """按最小依赖方式读取 `.env` 文件。

    参数:
    - path: `.env` 文件路径。

    返回:
    - 无返回值，直接将缺失的环境变量写入 `os.environ`。

    说明:
    - 仅在环境变量尚未存在时写入，便于外部部署环境覆盖本地默认值。
    """
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
    """应用运行配置集合。"""
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


settings = Settings(
    # 这里集中完成字符串到布尔值、整数等类型的转换，
    # 避免业务层重复解析同一份配置。
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
    mail_inbox_protocol=os.getenv("MAIL_INBOX_PROTOCOL", "imap").strip().lower() or "imap",
    imap_host=os.getenv("IMAP_HOST", ""),
    imap_port=int(os.getenv("IMAP_PORT", "993")),
    imap_user=os.getenv("IMAP_USER", ""),
    imap_password=os.getenv("IMAP_PASSWORD", ""),
    imap_use_tls=os.getenv("IMAP_USE_TLS", "false").lower() == "true",
    imap_use_ssl=os.getenv("IMAP_USE_SSL", "true").lower() == "true",
    pop3_host=os.getenv("POP3_HOST", ""),
    pop3_port=int(os.getenv("POP3_PORT", "110")),
    pop3_user=os.getenv("POP3_USER", ""),
    pop3_password=os.getenv("POP3_PASSWORD", ""),
    pop3_use_tls=os.getenv("POP3_USE_TLS", "false").lower() == "true",
    pop3_use_ssl=os.getenv("POP3_USE_SSL", "false").lower() == "true",
    mail_inbox_max_scan=int(os.getenv("MAIL_INBOX_MAX_SCAN", os.getenv("IMAP_MAX_UNSEEN_SCAN", "20"))),
    imap_max_unseen_scan=int(os.getenv("IMAP_MAX_UNSEEN_SCAN", "20")),
    mail_auto_poll_enabled=os.getenv("MAIL_AUTO_POLL_ENABLED", "true").lower() == "true",
    mail_auto_poll_interval_seconds=int(os.getenv("MAIL_AUTO_POLL_INTERVAL_SECONDS", "300")),
)
