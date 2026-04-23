from __future__ import annotations

"""数据库连接与会话管理。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    """向 FastAPI 依赖注入提供数据库会话。

    每次请求都会创建独立会话，并在请求结束后自动关闭，
    避免连接泄漏或不同请求之间的状态串扰。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
