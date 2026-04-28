from __future__ import annotations

"""用户管理辅助服务。"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.constants import ADMIN_ROLES
from app.models import User
from app.security import hash_password


def ensure_last_admin_not_removed(db: Session, target_user: User, new_role: str | None = None, new_active: bool | None = None) -> None:
    """保护系统中最后一个管理角色账号不被禁用或降级。

    系统管理员和管理员都拥有管理接口权限，因此只要系统中仍有一个启用的管理账号即可。
    """
    if target_user.role not in ADMIN_ROLES:
        return
    next_role = new_role if new_role is not None else target_user.role
    next_active = new_active if new_active is not None else target_user.is_active
    if next_role in ADMIN_ROLES and next_active:
        return
    remaining_admins = db.query(User).filter(User.role.in_(tuple(ADMIN_ROLES)), User.is_active.is_(True), User.id != target_user.id).count()
    if remaining_admins == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能禁用或降级系统中的最后一个管理角色账号")


def build_default_password_hash(default_password: str) -> str:
    """生成默认密码的摘要值。"""
    return hash_password(default_password)
