from __future__ import annotations

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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该延期申请已被其他审批结果生效")

    refreshed = db.query(DelayRequest).filter(DelayRequest.id == request_obj.id).first()
    if refreshed is None:
        raise HTTPException(status_code=404, detail="延期申请不存在")

    if next_status == "APPROVED" and approved_deadline is not None:
        task = db.query(Task).filter(Task.id == refreshed.task_id).first()
        if task:
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
