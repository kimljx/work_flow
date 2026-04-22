from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[assignment]


def _resolve_shanghai_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("Asia/Shanghai")
        except ZoneInfoNotFoundError:
            pass
    return timezone(timedelta(hours=8), name="Asia/Shanghai")


SHANGHAI_TZ = _resolve_shanghai_tz()


def shanghai_now() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def shanghai_now_naive() -> datetime:
    return shanghai_now().replace(tzinfo=None)


def to_shanghai_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
