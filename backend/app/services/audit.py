from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    operator_id: int | None,
    action_type: str,
    target_type: str,
    target_id: int | None,
    before: dict,
    after: dict,
    source_ip: str = "",
) -> None:
    db.add(
        AuditLog(
            operator_id=operator_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            before_json=json.dumps(before, ensure_ascii=False),
            after_json=json.dumps(after, ensure_ascii=False),
            source_ip=source_ip,
        )
    )
