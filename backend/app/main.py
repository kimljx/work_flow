from __future__ import annotations

"""FastAPI 应用入口。

负责完成以下启动期工作：
1. 初始化数据库与默认数据；
2. 注册跨域中间件与业务路由；
3. 在需要时启动后台邮件轮询线程；
4. 托管前端构建后的静态资源，便于离线环境只运行一个服务。
"""

import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import router
from app.bootstrap import bootstrap_database
from app.config import settings
from app.db import SessionLocal
from app.services.mail import poll_mailbox

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"

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


def _frontend_file(relative_path: str) -> Path:
    """返回前端构建产物中的目标文件路径。"""
    return FRONTEND_DIST_DIR / relative_path


def _serve_frontend_file(relative_path: str = "index.html") -> FileResponse:
    """返回前端静态文件响应。

    当离线发布包未包含前端构建产物时，明确给出错误提示，
    便于运维快速发现是“未构建前端”而不是“后端服务异常”。
    """
    target = _frontend_file(relative_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="前端静态资源不存在，请先执行前端构建或使用离线发布包。")
    return FileResponse(target)


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


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    """返回前端首页。"""
    return _serve_frontend_file()


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_entry(full_path: str) -> FileResponse:
    """为前端单页应用提供静态资源与路由回退。

    处理规则：
    - 如果请求的是已构建的静态文件，则直接返回该文件；
    - 如果请求的是前端页面路由，则统一回退到 `index.html`；
    - `/api`、`/docs`、`/redoc`、`/openapi.json` 等后端路径不在此处兜底。
    """
    reserved_prefixes = ("api/", "docs", "redoc", "openapi.json", "health")
    if not full_path or full_path in reserved_prefixes or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    static_target = _frontend_file(full_path)
    if static_target.exists() and static_target.is_file():
        return FileResponse(static_target)

    return _serve_frontend_file()
