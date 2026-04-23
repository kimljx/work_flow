from __future__ import annotations

"""用户管理辅助服务。"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password


def ensure_last_admin_not_removed(db: Session, target_user: User, new_role: str | None = None, new_active: bool | None = None) -> None:
    """保护系统中最后一个管理员不被禁用或降级。"""
    if target_user.role != "admin":
        return
    next_role = new_role if new_role is not None else target_user.role
    next_active = new_active if new_active is not None else target_user.is_active
    if next_role == "admin" and next_active:
        return
    remaining_admins = db.query(User).filter(User.role == "admin", User.is_active.is_(True), User.id != target_user.id).count()
    if remaining_admins == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能禁用或降级系统中的最后一个管理员")


def build_default_password_hash(default_password: str) -> str:
    """生成默认密码的摘要值。"""
    return hash_password(default_password)
