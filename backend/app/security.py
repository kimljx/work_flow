from __future__ import annotations

"""认证与鉴权工具。

负责密码摘要、JWT 生成与解析、当前用户识别以及管理员权限校验。
"""

import hashlib
from datetime import timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.timeutils import shanghai_now

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(raw_password: str) -> str:
    """对明文密码做 SHA-256 摘要。"""
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def verify_password(raw_password: str, password_hash: str) -> bool:
    """校验明文密码是否与数据库中的摘要一致。"""
    return hash_password(raw_password) == password_hash


def create_token(subject: str, token_type: str, expires_minutes: int) -> str:
    """生成访问令牌或刷新令牌。"""
    now = shanghai_now()
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    """解析 JWT，并返回载荷。"""
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从请求头中解析当前登录用户。"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少登录令牌")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录令牌无效") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录令牌类型错误")
    user = db.query(User).filter(User.id == int(payload["sub"]), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """要求当前用户必须是管理员，否则返回 403。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user
