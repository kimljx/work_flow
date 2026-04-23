from __future__ import annotations

"""FastAPI 应用入口。

负责完成以下启动期工作：
1. 初始化数据库与默认数据；
2. 注册跨域中间件与业务路由；
3. 在需要时启动后台邮件轮询线程；
4. 提供基础健康检查接口。
"""

import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.bootstrap import bootstrap_database
from app.config import settings
from app.db import SessionLocal
from app.services.mail import poll_mailbox

logger = logging.getLogger(__name__)

_mail_poll_stop_event = threading.Event()
_mail_poll_thread: threading.Thread | None = None


def _mail_poll_loop() -> None:
    """后台轮询邮箱并同步邮件动作。

    这里使用独立线程而不是阻塞主线程，避免影响 Web 接口响应。
    轮询间隔设置了最小值，防止因错误配置导致数据库和邮箱被过度请求。
    """
    interval = max(settings.mail_auto_poll_interval_seconds, 30)
    while not _mail_poll_stop_event.wait(interval):
        try:
            with SessionLocal() as db:
                result = poll_mailbox(db)
                logger.info("Auto mail poll result: %s", result)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto mail poll failed: %s", exc)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    """应用启动时初始化数据库，并按配置拉起自动收件线程。"""
    bootstrap_database()
    global _mail_poll_thread
    if settings.mail_auto_poll_enabled and _mail_poll_thread is None:
        _mail_poll_stop_event.clear()
        _mail_poll_thread = threading.Thread(target=_mail_poll_loop, name="mail-auto-poll", daemon=True)
        _mail_poll_thread.start()
        logger.info("Auto mail polling started, interval=%ss", max(settings.mail_auto_poll_interval_seconds, 30))


@app.on_event("shutdown")
def shutdown_event() -> None:
    """应用关闭时优雅停止后台轮询线程，避免进程悬挂。"""
    global _mail_poll_thread
    _mail_poll_stop_event.set()
    if _mail_poll_thread and _mail_poll_thread.is_alive():
        _mail_poll_thread.join(timeout=2)
    _mail_poll_thread = None


@app.get("/health")
def health() -> dict[str, str]:
    """提供部署健康检查接口。"""
    return {"status": "ok"}


app.include_router(router)
