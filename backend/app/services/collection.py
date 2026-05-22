from __future__ import annotations

"""邮件与 QAX 采集后台协调模块。

该模块把手动采集统一收口为单一后台任务，避免管理员重复点击、自动任务与手动任务并发时
同时操作邮箱或 QAX 页面。任务状态保存在进程内，供前端轮询并展示参与人维度的收集中进度。
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import TaskMember
from app.services.mail import poll_mailbox
from app.services.qax import collect_qax_status
from app.timeutils import shanghai_now_naive

_executor = ThreadPoolExecutor(max_workers=1)
_state_lock = Lock()
_running = False
_state: dict[str, Any] = {
    "running": False,
    "mode": "",
    "task_id": None,
    "message": "暂无采集任务",
    "status": "idle",
    "participants": [],
    "mail": {},
    "qax": {},
    "started_at": None,
    "finished_at": None,
}


def _state_snapshot() -> dict[str, Any]:
    """返回当前采集状态的浅拷贝，避免调用方直接修改全局状态。"""

    with _state_lock:
        return {
            **_state,
            "participants": [dict(item) for item in _state.get("participants", [])],
            "mail": dict(_state.get("mail") or {}),
            "qax": dict(_state.get("qax") or {}),
        }


def _update_state(**kwargs: Any) -> None:
    """线程安全更新采集状态。"""

    with _state_lock:
        _state.update(kwargs)


def _build_participants(db: Session, task_id: int | None) -> list[dict[str, Any]]:
    """按任务参与人初始化前端进度项。"""

    if not task_id:
        return []
    members = (
        db.query(TaskMember)
        .filter(TaskMember.task_id == task_id)
        .order_by(TaskMember.id.asc())
        .all()
    )
    return [
        {
            "user_id": item.user_id,
            "name": item.user.name if item.user else f"成员 #{item.user_id}",
            "status": "pending",
            "status_text": "等待收集",
            "detail": "",
        }
        for item in members
    ]


def _mark_participant(user_id: int, status: str, status_text: str, detail: str = "") -> None:
    """按成员更新采集进度，供任务详情弹窗实时展示。"""

    with _state_lock:
        participants = _state.get("participants") or []
        for item in participants:
            if item.get("user_id") == user_id:
                item.update({"status": status, "status_text": status_text, "detail": detail})
                break


def _mark_all(status: str, status_text: str, detail: str = "") -> None:
    """批量更新全部参与人的进度状态。"""

    with _state_lock:
        for item in _state.get("participants") or []:
            item.update({"status": status, "status_text": status_text, "detail": detail})


def _run_collect(mode: str, task_id: int | None) -> None:
    """后台执行采集任务，并在结束时释放单例运行锁。"""

    global _running
    try:
        with SessionLocal() as db:
            try:
                if mode in {"mail", "sync"}:
                    _mark_all("collecting", "邮件收集中")
                    _update_state(message="正在后台收取邮件")
                    mail_result = poll_mailbox(db)
                    db.commit()
                    _update_state(mail=mail_result)

                if mode in {"qax", "sync"}:
                    _mark_all("collecting", "QAX 收集中")
                    _update_state(message="正在后台采集 QAX 状态")
                    qax_result = collect_qax_status(
                        db,
                        task_id=task_id,
                        progress_callback=lambda user_id, text: _mark_participant(user_id, "collecting", text),
                    )
                    db.commit()
                    _update_state(qax=qax_result)

                _mark_all("done", "已更新")
                _update_state(
                    running=False,
                    status="success",
                    message="后台采集已完成",
                    finished_at=shanghai_now_naive().isoformat(sep=" ", timespec="seconds"),
                )
            except Exception as exc:  # pragma: no cover - 后台兜底，避免线程静默退出。
                db.rollback()
                _mark_all("failed", "收集失败", str(exc))
                _update_state(
                    running=False,
                    status="failed",
                    message=f"后台采集失败：{exc}",
                    finished_at=shanghai_now_naive().isoformat(sep=" ", timespec="seconds"),
                )
    finally:
        with _state_lock:
            _running = False


def start_collect(mode: str, task_id: int | None = None) -> dict[str, Any]:
    """启动一次后台采集；已有采集运行时直接返回当前状态。"""

    global _running
    safe_mode = mode if mode in {"mail", "qax", "sync"} else "sync"
    with _state_lock:
        if _running:
            return {
                **_state,
                "participants": [dict(item) for item in _state.get("participants", [])],
                "mail": dict(_state.get("mail") or {}),
                "qax": dict(_state.get("qax") or {}),
                "accepted": False,
                "message": "已有采集任务正在执行，本次请求已忽略",
            }
        _running = True

    with SessionLocal() as db:
        participants = _build_participants(db, task_id)

    _update_state(
        running=True,
        mode=safe_mode,
        task_id=task_id,
        message="后台采集已启动",
        status="running",
        participants=participants,
        mail={},
        qax={},
        started_at=shanghai_now_naive().isoformat(sep=" ", timespec="seconds"),
        finished_at=None,
    )
    _executor.submit(_run_collect, safe_mode, task_id)
    snapshot = _state_snapshot()
    snapshot["accepted"] = True
    return snapshot


def collect_state(task_id: int | None = None) -> dict[str, Any]:
    """读取当前后台采集状态，可按任务过滤参与人进度展示。"""

    snapshot = _state_snapshot()
    if task_id is not None and snapshot.get("task_id") not in {None, task_id}:
        return {
            **snapshot,
            "running": bool(snapshot.get("running")),
            "participants": [],
            "message": "已有其他采集任务正在执行",
        }
    return snapshot
