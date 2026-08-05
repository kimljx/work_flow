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
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import router
from app.bootstrap import bootstrap_database
from app.config import settings
from app.db import SessionLocal
from app.services.audit import cleanup_system_logs, write_system_log
from app.services.mail import cleanup_completed_task_mails, poll_mailbox
from app.services.notifications import create_due_reminders, create_overdue_task_reminders
from app.services.qax import collect_qax_status
from app.services.runtime_settings import load_runtime_settings
from app.timeutils import shanghai_now_naive

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
_due_remind_stop_event = threading.Event()
_due_remind_thread: threading.Thread | None = None
_overdue_remind_stop_event = threading.Event()
_overdue_remind_thread: threading.Thread | None = None
_system_log_cleanup_stop_event = threading.Event()
_system_log_cleanup_thread: threading.Thread | None = None
_completed_mail_cleanup_stop_event = threading.Event()
_completed_mail_cleanup_thread: threading.Thread | None = None


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
    while not _mail_poll_stop_event.wait(max(load_runtime_settings().mail_auto_poll_interval_seconds, 30)):
        runtime = load_runtime_settings()
        if not runtime.mail_auto_poll_enabled:
            continue
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

    清理开关、周期与保留天数来自计划任务运行配置，便于系统管理员按部署规模和磁盘容量调整。
    """

    while not _system_log_cleanup_stop_event.wait(max(load_runtime_settings().system_log_cleanup_interval_seconds, 300)):
        runtime = load_runtime_settings()
        if not runtime.system_log_cleanup_enabled:
            continue
        try:
            with SessionLocal() as db:
                deleted_count = cleanup_system_logs(db, runtime.system_log_retention_days)
                write_system_log(
                    db,
                    operator_id=None,
                    action_type="AUTO_CLEANUP_SYSTEM_LOG",
                    target_type="SystemLog",
                    target_id=None,
                    before={},
                    after={"deleted_count": deleted_count, "retention_days": runtime.system_log_retention_days},
                    log_level="INFO",
                    module_name="scheduler.system-log",
                    message=f"自动清理系统日志完成，删除 {deleted_count} 条过期记录",
                    detail={
                        "deleted_count": deleted_count,
                        "retention_days": runtime.system_log_retention_days,
                        "interval_seconds": runtime.system_log_cleanup_interval_seconds,
                    },
                )
                db.commit()
                logger.info("Auto system log cleanup result: deleted=%s retention_days=%s", deleted_count, runtime.system_log_retention_days)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto system log cleanup failed: %s", exc)


def _completed_mail_cleanup_loop() -> None:
    """每天清理超过保留天数的已完成任务邮件回执。"""

    last_run_date: date | None = None
    while not _completed_mail_cleanup_stop_event.wait(30):
        runtime = load_runtime_settings()
        if not runtime.completed_mail_cleanup_enabled:
            continue
        now = shanghai_now_naive()
        if now.strftime("%H:%M") != "02:30" or last_run_date == now.date():
            continue
        try:
            with SessionLocal() as db:
                result = cleanup_completed_task_mails(db, runtime.completed_mail_cleanup_retention_days)
                write_system_log(
                    db,
                    operator_id=None,
                    action_type="AUTO_CLEANUP_COMPLETED_TASK_MAILS",
                    target_type="MailInbox",
                    target_id=None,
                    before={},
                    after=result,
                    log_level="INFO" if result.get("failed_count", 0) == 0 else "WARNING",
                    module_name="scheduler.mail-cleanup",
                    message=(
                        f"自动清理已完成任务邮件完成，扫描 {result.get('task_count', 0)} 个任务，"
                        f"删除 {result.get('deleted_count', 0)} 封，"
                        f"清理落库记录 {result.get('deleted_record_count', 0)} 条，"
                        f"失败 {result.get('failed_count', 0)} 封"
                    ),
                    detail=result,
                )
                db.commit()
                last_run_date = now.date()
                logger.info("Auto completed task mail cleanup result: %s", result)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto completed task mail cleanup failed: %s", exc)


def _qax_collect_loop() -> None:
    """按 cron 配置定时执行 QAX 状态采集并写入系统日志。"""

    check_interval_seconds = 30
    next_run_at: datetime | None = None
    last_interval_seconds: int | None = None

    while not _qax_collect_stop_event.wait(check_interval_seconds):
        runtime = load_runtime_settings()
        if not runtime.qax_auto_collect_enabled:
            next_run_at = None
            last_interval_seconds = None
            continue
        interval_seconds = max(runtime.qax_auto_collect_interval_seconds, 30)
        now = shanghai_now_naive()
        if next_run_at is None:
            next_run_at = now + timedelta(seconds=interval_seconds)
            last_interval_seconds = interval_seconds
            continue
        if last_interval_seconds != interval_seconds:
            next_run_at = now + timedelta(seconds=interval_seconds)
            last_interval_seconds = interval_seconds
        if now < next_run_at:
            continue
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
                    detail={"interval_seconds": interval_seconds, **result},
                )
                db.commit()
                logger.info("Auto qax collect result: %s", result)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto qax collect failed: %s", exc)
            try:
                with SessionLocal() as db:
                    write_system_log(
                        db,
                        operator_id=None,
                        action_type="AUTO_COLLECT_QAX_STATUS",
                        target_type="Notification",
                        target_id=None,
                        before={},
                        after={"status": "failed"},
                        log_level="ERROR",
                        module_name="scheduler.qax",
                        message="自动采集 QAX 状态失败",
                        detail={"interval_seconds": interval_seconds, "status": "failed", "message": str(exc)},
                    )
                    db.commit()
            except Exception:
                logger.exception("Auto qax collect failure log write failed")
        finally:
            next_run_at = shanghai_now_naive() + timedelta(seconds=interval_seconds)


def _due_remind_loop() -> None:
    """每天在运行时设置的时间点生成主任务提前提醒。"""
    last_run_date: date | None = None
    while not _due_remind_stop_event.wait(30):
        runtime = load_runtime_settings()
        if not runtime.due_remind_enabled:
            continue
        now = shanghai_now_naive()
        if now.strftime("%H:%M") != runtime.due_remind_run_at or last_run_date == now.date():
            continue
        try:
            with SessionLocal() as db:
                created_count = create_due_reminders(db)
                write_system_log(
                    db,
                    operator_id=None,
                    action_type="AUTO_CREATE_DUE_REMINDERS",
                    target_type="Task",
                    target_id=None,
                    before={},
                    after={"created_count": created_count, "run_at": runtime.due_remind_run_at},
                    log_level="INFO",
                    module_name="scheduler.due-remind",
                    message=f"自动生成主任务提前提醒，新增 {created_count} 条",
                    detail={"created_count": created_count, "run_at": runtime.due_remind_run_at},
                )
                db.commit()
                last_run_date = now.date()
                logger.info("Auto due reminder result: created=%s run_at=%s", created_count, runtime.due_remind_run_at)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto due reminder failed: %s", exc)


def _overdue_remind_loop() -> None:
    """每天在运行时设置的时间点提醒延期或已过截止时间的未完成主任务。"""
    last_run_date: date | None = None
    while not _overdue_remind_stop_event.wait(30):
        runtime = load_runtime_settings()
        if not runtime.overdue_remind_enabled:
            continue
        now = shanghai_now_naive()
        if now.strftime("%H:%M") != runtime.overdue_remind_run_at or last_run_date == now.date():
            continue
        try:
            with SessionLocal() as db:
                created_count = create_overdue_task_reminders(db)
                write_system_log(
                    db,
                    operator_id=None,
                    action_type="AUTO_CREATE_OVERDUE_REMINDERS",
                    target_type="Task",
                    target_id=None,
                    before={},
                    after={"created_count": created_count, "run_at": runtime.overdue_remind_run_at},
                    log_level="INFO",
                    module_name="scheduler.overdue-remind",
                    message=f"自动生成延期未完成任务提醒，新增 {created_count} 条",
                    detail={"created_count": created_count, "run_at": runtime.overdue_remind_run_at},
                )
                db.commit()
                last_run_date = now.date()
                logger.info("Auto overdue reminder result: created=%s run_at=%s", created_count, runtime.overdue_remind_run_at)
        except Exception as exc:  # pragma: no cover
            logger.exception("Auto overdue reminder failed: %s", exc)


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
    global _mail_poll_thread, _qax_collect_thread, _due_remind_thread, _overdue_remind_thread, _system_log_cleanup_thread, _completed_mail_cleanup_thread
    if _mail_poll_thread is None:
        _mail_poll_stop_event.clear()
        _mail_poll_thread = threading.Thread(target=_mail_poll_loop, name="mail-auto-poll", daemon=True)
        _mail_poll_thread.start()
        logger.info("Auto mail polling started")
    if _qax_collect_thread is None:
        _qax_collect_stop_event.clear()
        _qax_collect_thread = threading.Thread(target=_qax_collect_loop, name="qax-auto-collect", daemon=True)
        _qax_collect_thread.start()
        logger.info("Auto qax collect started")
    if _due_remind_thread is None:
        _due_remind_stop_event.clear()
        _due_remind_thread = threading.Thread(target=_due_remind_loop, name="due-remind", daemon=True)
        _due_remind_thread.start()
        logger.info("Auto due reminder started")
    if _overdue_remind_thread is None:
        _overdue_remind_stop_event.clear()
        _overdue_remind_thread = threading.Thread(target=_overdue_remind_loop, name="overdue-remind", daemon=True)
        _overdue_remind_thread.start()
        logger.info("Auto overdue reminder started")
    if _system_log_cleanup_thread is None:
        _system_log_cleanup_stop_event.clear()
        _system_log_cleanup_thread = threading.Thread(target=_system_log_cleanup_loop, name="system-log-cleanup", daemon=True)
        _system_log_cleanup_thread.start()
        runtime = load_runtime_settings()
        logger.info(
            "Auto system log cleanup started, enabled=%s retention_days=%s interval=%ss",
            runtime.system_log_cleanup_enabled,
            runtime.system_log_retention_days,
            max(runtime.system_log_cleanup_interval_seconds, 300),
        )
    if _completed_mail_cleanup_thread is None:
        _completed_mail_cleanup_stop_event.clear()
        _completed_mail_cleanup_thread = threading.Thread(target=_completed_mail_cleanup_loop, name="completed-mail-cleanup", daemon=True)
        _completed_mail_cleanup_thread.start()
        runtime = load_runtime_settings()
        logger.info(
            "Auto completed task mail cleanup started, enabled=%s retention_days=%s",
            runtime.completed_mail_cleanup_enabled,
            runtime.completed_mail_cleanup_retention_days,
        )


@app.on_event("shutdown")
def shutdown_event() -> None:
    """应用关闭时优雅停止后台轮询线程，避免进程悬挂。"""
    global _mail_poll_thread, _qax_collect_thread, _due_remind_thread, _overdue_remind_thread, _system_log_cleanup_thread, _completed_mail_cleanup_thread
    _mail_poll_stop_event.set()
    _qax_collect_stop_event.set()
    _due_remind_stop_event.set()
    _overdue_remind_stop_event.set()
    _system_log_cleanup_stop_event.set()
    _completed_mail_cleanup_stop_event.set()
    if _mail_poll_thread and _mail_poll_thread.is_alive():
        _mail_poll_thread.join(timeout=2)
    if _qax_collect_thread and _qax_collect_thread.is_alive():
        _qax_collect_thread.join(timeout=2)
    if _due_remind_thread and _due_remind_thread.is_alive():
        _due_remind_thread.join(timeout=2)
    if _overdue_remind_thread and _overdue_remind_thread.is_alive():
        _overdue_remind_thread.join(timeout=2)
    if _system_log_cleanup_thread and _system_log_cleanup_thread.is_alive():
        _system_log_cleanup_thread.join(timeout=2)
    if _completed_mail_cleanup_thread and _completed_mail_cleanup_thread.is_alive():
        _completed_mail_cleanup_thread.join(timeout=2)
    _mail_poll_thread = None
    _qax_collect_thread = None
    _due_remind_thread = None
    _overdue_remind_thread = None
    _system_log_cleanup_thread = None
    _completed_mail_cleanup_thread = None


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
