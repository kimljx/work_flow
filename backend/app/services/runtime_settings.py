from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, settings


RUNTIME_SETTINGS_PATH = PROJECT_ROOT / "config" / "runtime-settings.json"


@dataclass
class RuntimeSettings:
    mail_auto_poll_enabled: bool = settings.mail_auto_poll_enabled
    mail_auto_poll_interval_seconds: int = settings.mail_auto_poll_interval_seconds
    mail_inbox_max_scan: int = settings.mail_inbox_max_scan
    due_remind_enabled: bool = True
    due_remind_run_at: str = settings.remind_daily_run_at
    overdue_remind_enabled: bool = True
    overdue_remind_run_at: str = "09:00"
    qax_auto_collect_enabled: bool = bool((settings.qax_collect_cron or "").strip())
    qax_auto_collect_interval_seconds: int = 3600
    mail_scan_baseline_at: str = ""
    qax_browser_visible: bool = not settings.qax_browser_headless


def _default_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        mail_auto_poll_enabled=settings.mail_auto_poll_enabled,
        mail_auto_poll_interval_seconds=settings.mail_auto_poll_interval_seconds,
        mail_inbox_max_scan=settings.mail_inbox_max_scan,
        due_remind_enabled=True,
        due_remind_run_at=settings.remind_daily_run_at,
        overdue_remind_enabled=True,
        overdue_remind_run_at="09:00",
        qax_auto_collect_enabled=bool((settings.qax_collect_cron or "").strip()),
        qax_auto_collect_interval_seconds=3600,
        mail_scan_baseline_at="",
        qax_browser_visible=not settings.qax_browser_headless,
    )


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
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


def load_runtime_settings() -> RuntimeSettings:
    current = _default_runtime_settings()
    if not RUNTIME_SETTINGS_PATH.exists():
        return current
    try:
        raw = json.loads(RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return current
    current.mail_auto_poll_enabled = _coerce_bool(raw.get("mail_auto_poll_enabled"), current.mail_auto_poll_enabled)
    current.mail_auto_poll_interval_seconds = _coerce_int(
        raw.get("mail_auto_poll_interval_seconds"),
        current.mail_auto_poll_interval_seconds,
        30,
    )
    current.mail_inbox_max_scan = _coerce_int(raw.get("mail_inbox_max_scan"), current.mail_inbox_max_scan, 1)
    current.due_remind_enabled = _coerce_bool(raw.get("due_remind_enabled"), current.due_remind_enabled)
    current.due_remind_run_at = _coerce_time(raw.get("due_remind_run_at"), current.due_remind_run_at)
    current.overdue_remind_enabled = _coerce_bool(raw.get("overdue_remind_enabled"), current.overdue_remind_enabled)
    current.overdue_remind_run_at = _coerce_time(raw.get("overdue_remind_run_at"), current.overdue_remind_run_at)
    current.qax_auto_collect_enabled = _coerce_bool(raw.get("qax_auto_collect_enabled"), current.qax_auto_collect_enabled)
    current.qax_auto_collect_interval_seconds = _coerce_int(
        raw.get("qax_auto_collect_interval_seconds"),
        current.qax_auto_collect_interval_seconds,
        30,
    )
    current.mail_scan_baseline_at = str(raw.get("mail_scan_baseline_at") or "").strip()
    current.qax_browser_visible = _coerce_bool(raw.get("qax_browser_visible"), current.qax_browser_visible)
    return current


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
    )
    RUNTIME_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_SETTINGS_PATH.write_text(json.dumps(asdict(updated), ensure_ascii=False, indent=2), encoding="utf-8")
    return updated


def runtime_settings_dict() -> dict[str, Any]:
    return asdict(load_runtime_settings())
