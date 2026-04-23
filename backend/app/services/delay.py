from __future__ import annotations

"""延期审批服务。"""

import json
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import DelayRequest, DelayRequestEvent, Task
from app.timeutils import shanghai_now_naive


def apply_delay_decision(
    db: Session,
    request_obj: DelayRequest,
    admin_id: int,
    request_id: str,
    action: str,
    channel: str,
    version: int,
    remark: str = "",
    approved_deadline: datetime | None = None,
) -> tuple[str, DelayRequest]:
    """执行延期审批，并保证幂等与并发安全。

    返回:
    - 第一个值为处理结果编码，例如 `APPLIED`、`IDEMPOTENT_REPLAY`。
    - 第二个值为审批后的延期申请对象。
    """
    idempotency_key = f"{request_id}+{admin_id}" if channel == "web" else request_id
    replay = (
        db.query(DelayRequestEvent)
        .filter(
            DelayRequestEvent.request_id == request_obj.id,
            DelayRequestEvent.idempotency_key == idempotency_key,
            DelayRequestEvent.event_type == "APPLIED",
        )
        .first()
    )
    if replay:
        # 同一审批请求重复提交时直接返回重放结果，避免二次落库。
        return "IDEMPOTENT_REPLAY", request_obj

    next_status = "APPROVED" if action == "APPROVE" else "REJECTED"
    result = db.execute(
        update(DelayRequest)
        .where(
            DelayRequest.id == request_obj.id,
            DelayRequest.approval_status == "PENDING",
            DelayRequest.version == version,
        )
        .values(
            approval_status=next_status,
            approver_id=admin_id,
            approved_deadline=approved_deadline,
            approve_remark=remark,
            decision_token=uuid.uuid4().hex,
            idempotency_key=idempotency_key,
            version=DelayRequest.version + 1,
            decided_by_channel=channel,
            decided_at=shanghai_now_naive(),
        )
    )
    if result.rowcount == 0:
        # 通过版本号与待审批状态双条件更新，确保只有首个有效审批能生效。
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该延期申请已被其他审批结果生效")

    refreshed = db.query(DelayRequest).filter(DelayRequest.id == request_obj.id).first()
    if refreshed is None:
        raise HTTPException(status_code=404, detail="延期申请不存在")

    if next_status == "APPROVED" and approved_deadline is not None:
        task = db.query(Task).filter(Task.id == refreshed.task_id).first()
        if task:
            # 审批通过后同步更新任务结束时间，并重新计算延期天数。
            task.delay_days = max((approved_deadline.date() - task.end_at.date()).days, 0)
            task.end_at = approved_deadline

    db.add(
        DelayRequestEvent(
            request_id=request_obj.id,
            event_type="APPLIED",
            idempotency_key=idempotency_key,
            payload_json=json.dumps(
                {
                    "action": action,
                    "channel": channel,
                    "remark": remark,
                    "approved_deadline": approved_deadline.isoformat() if approved_deadline else None,
                },
                ensure_ascii=False,
            ),
        )
    )
    return "APPLIED", refreshed
