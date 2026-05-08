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
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import router
from app.bootstrap import bootstrap_database
from app.config import settings
from app.db import SessionLocal
from app.services.audit import cleanup_system_logs, write_system_log
from app.services.mail import poll_mailbox
from app.services.qax import collect_qax_status

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

_mail_poll_stop_event = threading.Event()
_mail_poll_thread: threading.Thread | None = None
_qax_collect_stop_event = threading.Event()
_qax_collect_thread: threading.Thread | None = None
_system_log_cleanup_stop_event = threading.Event()
_system_log_cleanup_thread: threading.Thread | None = None


def _cron_field_matches(field: str, value: int, *, minimum: int, maximum: int) -> bool:
    """判断单个 cron 字段是否命中当前值。

    支持 `*`、`*/n`、`a`、`a,b`、`a-b`、`a-b/n` 这些当前运维配置最常见的写法，
    既能兼容现有 `0 * * * *`，也避免未来改成更细粒度计划时必须改代码。
    """

    normalized = (field or "").strip()
    if not normalized or normalized == "*":
        return True
    for part in normalized.split(","):
        token = part.strip()
        if not token:
            continue
        step = 1
        if "/" in token:
            token, step_text = token.split("/", 1)
            step = max(int(step_text), 1)
        if token == "*":
            start, end = minimum, maximum
        elif "-" in token:
            start_text, end_text = token.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            target = int(token)
            if target == value:
                return True
            continue
        if start <= value <= end and (value - start) % step == 0:
            return True
    return False


def _cron_matches_now(cron_expr: str, current: datetime) -> bool:
    """判断当前时间是否命中 QAX 定时扫描表达式。"""

    fields = (cron_expr or "").split()
    if len(fields) != 5:
        return False
    minute, hour, day, month, weekday = fields
    cron_weekday = (current.weekday() + 1) % 7
    return (
        _cron_field_matches(minute, current.minute, minimum=0, maximum=59)
        and _cron_field_matches(hour, current.hour, minimum=0, maximum=23)
        and _cron_field_matches(day, current.day, minimum=1, maximum=31)
        and _cron_field_matches(month, current.month, minimum=1, maximum=12)
        and _cron_field_matches(weekday.replace("7", "0"), cron_weekday, minimum=0, maximum=6)
    )


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
                write_system_log(
                    db,
                    operator_id=None,
                    action_type="AUTO_MAIL_POLL",
                    target_type="MailInbox",
                    target_id=None,
                    before={},
                    after={"result": result},
                    log_level="INFO" if result.get("status") == "success" else "WARNING",
                    module_name="scheduler.mail",
                    message=f"自动收件执行完成，状态：{result.get('status')}",
                    detail=result,
                )
                db.commit()
                logger.info("Auto mail poll result: %s", result)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto mail poll failed: %s", exc)


def _system_log_cleanup_loop() -> None:
    """后台定时清理过期系统日志。

    清理周期与保留天数都来自配置文件，默认每天清理一次、保留 60 天，
    便于系统管理员按部署规模和磁盘容量调整。
    """

    interval = max(settings.system_log_cleanup_interval_seconds, 300)
    while not _system_log_cleanup_stop_event.wait(interval):
        try:
            with SessionLocal() as db:
                deleted_count = cleanup_system_logs(db, settings.system_log_retention_days)
                write_system_log(
                    db,
                    operator_id=None,
                    action_type="AUTO_CLEANUP_SYSTEM_LOG",
                    target_type="SystemLog",
                    target_id=None,
                    before={},
                    after={"deleted_count": deleted_count, "retention_days": settings.system_log_retention_days},
                    log_level="INFO",
                    module_name="scheduler.system-log",
                    message=f"自动清理系统日志完成，删除 {deleted_count} 条过期记录",
                    detail={
                        "deleted_count": deleted_count,
                        "retention_days": settings.system_log_retention_days,
                        "interval_seconds": interval,
                    },
                )
                db.commit()
                logger.info("Auto system log cleanup result: deleted=%s retention_days=%s", deleted_count, settings.system_log_retention_days)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto system log cleanup failed: %s", exc)


def _qax_collect_loop() -> None:
    """按 cron 配置定时执行 QAX 状态采集并写入系统日志。"""

    cron_expr = (settings.qax_collect_cron or "").strip()
    last_run_key = ""
    while not _qax_collect_stop_event.wait(15):
        current = datetime.now()
        current_key = current.strftime("%Y-%m-%d %H:%M")
        if current_key == last_run_key:
            continue
        if not _cron_matches_now(cron_expr, current):
            continue
        last_run_key = current_key
        try:
            with SessionLocal() as db:
                result = collect_qax_status(db)
                write_system_log(
                    db,
                    operator_id=None,
                    action_type="AUTO_COLLECT_QAX_STATUS",
                    target_type="Notification",
                    target_id=None,
                    before={},
                    after={
                        "status": result.get("status"),
                        "processed_count": result.get("processed_count", 0),
                        "updated_count": result.get("updated_count", 0),
                        "failed_count": result.get("failed_count", 0),
                    },
                    log_level="INFO" if result.get("status") == "success" else "WARNING",
                    module_name="scheduler.qax",
                    message=f"自动采集 QAX 状态完成，结果：{result.get('status')}",
                    detail={"cron": cron_expr, **result},
                )
                db.commit()
                logger.info("Auto qax collect result: %s", result)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto qax collect failed: %s", exc)


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
    return FileResponse(target, headers=FRONTEND_NO_CACHE_HEADERS)


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
    global _mail_poll_thread, _qax_collect_thread, _system_log_cleanup_thread
    if settings.mail_auto_poll_enabled and _mail_poll_thread is None:
        _mail_poll_stop_event.clear()
        _mail_poll_thread = threading.Thread(target=_mail_poll_loop, name="mail-auto-poll", daemon=True)
        _mail_poll_thread.start()
        logger.info("Auto mail polling started, interval=%ss", max(settings.mail_auto_poll_interval_seconds, 30))
    if settings.qax_collect_cron.strip() and _qax_collect_thread is None:
        _qax_collect_stop_event.clear()
        _qax_collect_thread = threading.Thread(target=_qax_collect_loop, name="qax-auto-collect", daemon=True)
        _qax_collect_thread.start()
        logger.info("Auto qax collect started, cron=%s", settings.qax_collect_cron)
    if _system_log_cleanup_thread is None:
        _system_log_cleanup_stop_event.clear()
        _system_log_cleanup_thread = threading.Thread(target=_system_log_cleanup_loop, name="system-log-cleanup", daemon=True)
        _system_log_cleanup_thread.start()
        logger.info(
            "Auto system log cleanup started, retention_days=%s interval=%ss",
            settings.system_log_retention_days,
            max(settings.system_log_cleanup_interval_seconds, 300),
        )


@app.on_event("shutdown")
def shutdown_event() -> None:
    """应用关闭时优雅停止后台轮询线程，避免进程悬挂。"""
    global _mail_poll_thread, _qax_collect_thread, _system_log_cleanup_thread
    _mail_poll_stop_event.set()
    _qax_collect_stop_event.set()
    _system_log_cleanup_stop_event.set()
    if _mail_poll_thread and _mail_poll_thread.is_alive():
        _mail_poll_thread.join(timeout=2)
    if _qax_collect_thread and _qax_collect_thread.is_alive():
        _qax_collect_thread.join(timeout=2)
    if _system_log_cleanup_thread and _system_log_cleanup_thread.is_alive():
        _system_log_cleanup_thread.join(timeout=2)
    _mail_poll_thread = None
    _qax_collect_thread = None
    _system_log_cleanup_thread = None


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
        return FileResponse(static_target, headers=FRONTEND_NO_CACHE_HEADERS)

    return _serve_frontend_file()
