from __future__ import annotations

"""系统日志写入与清理服务。"""

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.timeutils import shanghai_now_naive


def _to_json_text(payload: dict | list | str | int | float | bool | None, default: str) -> str:
    """将系统日志附加信息稳定序列化为 JSON 文本。"""

    if payload in (None, "", {}, []):
        return default
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


def write_system_log(
    db: Session,
    operator_id: int | None,
    action_type: str,
    target_type: str,
    target_id: int | None,
    before: dict,
    after: dict,
    source_ip: str = "",
    *,
    log_level: str = "INFO",
    module_name: str = "system",
    message: str = "",
    detail: dict | list | str | int | float | bool | None = None,
) -> None:
    """写入一条系统日志。

    参数:
    - db: 当前数据库会话。
    - operator_id: 操作人 ID；后台线程或系统自维护动作可为空。
    - action_type: 动作类型，例如 `CREATE_TASK`、`AUTO_MAIL_POLL`。
    - target_type: 影响对象类型，例如 `Task`、`MailInbox`、`SystemLog`。
    - target_id: 影响对象主键，可为空。
    - before: 动作前快照，便于管理员回看关键字段变更。
    - after: 动作后快照，便于管理员定位最终结果。
    - source_ip: 请求来源 IP；后台线程场景可留空。
    - log_level: 日志等级，默认 `INFO`。
    - module_name: 日志来源模块，例如 `api.task`、`scheduler.mail`。
    - message: 人类可读摘要，优先用于列表页快速扫描。
    - detail: 扩展详情，可存放错误文本、统计摘要、上下文参数等。
    """

    db.add(
        AuditLog(
            operator_id=operator_id,
            log_level=(log_level or "INFO").upper(),
            module_name=module_name or "system",
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            message=message or action_type,
            detail_json=_to_json_text(detail, "{}"),
            before_json=_to_json_text(before, "{}"),
            after_json=_to_json_text(after, "{}"),
            source_ip=source_ip,
        )
    )


def write_audit(
    db: Session,
    operator_id: int | None,
    action_type: str,
    target_type: str,
    target_id: int | None,
    before: dict,
    after: dict,
    source_ip: str = "",
    *,
    log_level: str = "INFO",
    module_name: str = "api",
    message: str = "",
    detail: dict | list | str | int | float | bool | None = None,
) -> None:
    """兼容旧调用方式的系统日志写入入口。

    当前仓库已有大量 `write_audit(...)` 调用。这里保留原函数名，
    避免一次性改动过大；但其语义已经统一升级为系统日志写入。
    """

    summary = message or (f"{action_type} {target_type}#{target_id}" if target_id is not None else f"{action_type} {target_type}")
    default_detail = detail if detail not in (None, "") else {"before": before, "after": after}
    write_system_log(
        db=db,
        operator_id=operator_id,
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        before=before,
        after=after,
        source_ip=source_ip,
        log_level=log_level,
        module_name=module_name,
        message=summary,
        detail=default_detail,
    )


def cleanup_system_logs(db: Session, retention_days: int) -> int:
    """删除保留期之外的系统日志，并返回删除数量。

    说明:
    - 清理动作本身会在调用方结束后再写入一条新的系统日志，
      这样既能避免被本次删除误删，也便于管理员持续追踪保留策略是否生效。
    """

    safe_retention_days = max(int(retention_days), 1)
    cutoff = shanghai_now_naive() - timedelta(days=safe_retention_days)
    stale_logs = db.query(AuditLog).filter(AuditLog.created_at < cutoff).all()
    deleted_count = len(stale_logs)
    if deleted_count == 0:
        return 0
    stale_ids = [item.id for item in stale_logs]
    db.query(AuditLog).filter(AuditLog.id.in_(stale_ids)).delete(synchronize_session=False)
    return deleted_count
