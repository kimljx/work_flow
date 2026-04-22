from __future__ import annotations

import csv
import io
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import (
    DELAY_STATUS_LABELS,
    MAIL_ACTION_STATUS_LABELS,
    MAIL_EVENT_STATUS_LABELS,
    MEMBER_ROLE_LABELS,
    NOTIFICATION_CHANNEL_LABELS,
    NOTIFICATION_STATUS_LABELS,
    NOTIFICATION_TYPE_LABELS,
    PRIORITY_LABELS,
    READ_STATUS_LABELS,
    ROLE_LABELS,
    TEMPLATE_NOTIFY_TYPE_OPTIONS,
    TASK_STATUS_LABELS,
)
from app.db import get_db
from app.models import AuditLog, DelayRequest, MailAction, MailEvent, Notification, NotificationRecipient, Task, TaskMember, TaskMilestone, TaskStatusEvent, Template, User
from app.schemas import (
    ApiMessage,
    AuditOut,
    DashboardSummary,
    DelayDecisionRequest,
    DelayRequestCreate,
    LoginRequest,
    MailEventOut,
    NotificationOut,
    RefreshRequest,
    TaskCreate,
    TaskDetailOut,
    TaskOut,
    TaskStatusUpdate,
    TemplateCreate,
    TemplatePreviewRequest,
    TokenPair,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.security import create_token, decode_token, get_current_user, require_admin, verify_password
from app.services.audit import write_audit
from app.services.delay import apply_delay_decision
from app.services.mail import diagnose_imap_settings, diagnose_mail_settings, initialize_mail_scan_baseline, poll_mailbox
from app.services.notifications import create_due_reminders, create_notification_with_recipients
from app.services.templates import sort_templates, template_matches
from app.timeutils import shanghai_now_naive
from app.services.users import build_default_password_hash, ensure_last_admin_not_removed

router = APIRouter(prefix="/api/v1")


def task_status_text(status: str) -> str:
    return TASK_STATUS_LABELS.get(status, status)


def task_status_display(task: Task) -> str:
    text = task_status_text(task.main_status)
    if task.delay_days > 0:
        return f"{text}（延期{task.delay_days}天）"
    return text


def infer_task_status_by_time(start_at: datetime, end_at: datetime, now: datetime | None = None) -> str:
    current = now or shanghai_now_naive()
    if current < start_at:
        return "not_started"
    if current >= end_at:
        return "done"
    return "in_progress"


def notification_channel_text(channel: str) -> str:
    return NOTIFICATION_CHANNEL_LABELS.get(channel, channel)


def notification_status_text(status: str) -> str:
    return NOTIFICATION_STATUS_LABELS.get(status, status)


def read_status_text(status: str) -> str:
    return READ_STATUS_LABELS.get(status, status)


def serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        role_text=ROLE_LABELS.get(user.role, user.role),
        name=user.name,
        email=user.email,
        ip_address=user.ip_address,
        is_active=user.is_active,
    )


def serialize_task(task: Task, db: Session) -> TaskOut:
    members = db.query(TaskMember).filter(TaskMember.task_id == task.id).all()
    owner_name = next((item.user.name for item in members if item.member_role == "owner" and item.user), "")
    participant_count = sum(1 for item in members if item.member_role == "participant")
    recipients = (
        db.query(NotificationRecipient)
        .join(Notification, NotificationRecipient.notification_id == Notification.id)
        .filter(Notification.task_id == task.id)
        .all()
    )
    delivered_count = sum(1 for item in recipients if item.delivery_status == "delivered")
    return TaskOut(
        id=task.id,
        title=task.title,
        content=task.content,
        remark=task.remark,
        priority=task.priority,
        main_status=task.main_status,
        delay_days=task.delay_days,
        state_locked=task.state_locked,
        due_remind_days=task.due_remind_days,
        start_at=task.start_at,
        end_at=task.end_at,
        planned_minutes=task.planned_minutes,
        actual_minutes=task.actual_minutes,
        status_text=task_status_display(task),
        priority_text=PRIORITY_LABELS.get(task.priority, task.priority),
        owner_name=owner_name,
        participant_count=participant_count,
        notification_total=len(recipients),
        delivered_count=delivered_count,
        completed_member_count=1 if task.main_status == "done" else 0,
    )


def serialize_notification(notification: Notification, db: Session) -> NotificationOut:
    recipients = db.query(NotificationRecipient).filter(NotificationRecipient.notification_id == notification.id).all()
    task_title = ""
    if notification.task_id:
        task = db.query(Task).filter(Task.id == notification.task_id).first()
        if task:
            task_title = task.title
    return NotificationOut(
        id=notification.id,
        task_id=notification.task_id,
        task_title=task_title,
        channel=notification.channel,
        notify_type=notification.notify_type,
        notify_type_text=NOTIFICATION_TYPE_LABELS.get(notification.notify_type, notification.notify_type),
        status=notification.status,
        channel_text=notification_channel_text(notification.channel),
        status_text=notification_status_text(notification.status),
        recipient_total=len(recipients),
        delivered_count=sum(1 for item in recipients if item.delivery_status == "delivered"),
        read_count=sum(1 for item in recipients if item.read_status == "read"),
        retry_total=sum(item.retry_count for item in recipients),
        last_error=next((item.last_error for item in recipients if item.last_error), ""),
        created_at=notification.created_at,
    )


def serialize_mail_event(mail_event: MailEvent, db: Session) -> MailEventOut:
    template = db.query(Template).filter(Template.id == mail_event.resolved_template_id).first() if mail_event.resolved_template_id else None
    action = db.query(MailAction).filter(MailAction.mail_event_id == mail_event.id).order_by(MailAction.id.desc()).first()
    task = db.query(Task).filter(Task.id == action.target_task_id).first() if action and action.target_task_id else None
    notify_type = template.notify_type if template else ""
    return MailEventOut(
        id=mail_event.id,
        message_id=mail_event.message_id,
        from_addr=mail_event.from_addr,
        subject=mail_event.subject,
        body_digest=mail_event.body_digest,
        process_status=mail_event.process_status,
        process_status_text=MAIL_EVENT_STATUS_LABELS.get(mail_event.process_status, mail_event.process_status),
        template_name=template.name if template else "",
        notify_type=notify_type,
        notify_type_text=NOTIFICATION_TYPE_LABELS.get(notify_type, notify_type),
        task_id=action.target_task_id if action else None,
        task_title=task.title if task else "",
        action_type=action.action_type if action else "",
        action_status=action.action_status if action else "",
        action_status_text=MAIL_ACTION_STATUS_LABELS.get(action.action_status, action.action_status) if action else "",
        action_result_json=action.action_result_json if action else "",
        created_at=mail_event.created_at,
    )


@router.post("/auth/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.query(User).filter(User.username == payload.username, User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return TokenPair(
        access_token=create_token(str(user.id), "access", settings.access_token_expire_minutes),
        refresh_token=create_token(str(user.id), "refresh", settings.refresh_token_expire_minutes),
    )


@router.post("/auth/refresh", response_model=TokenPair)
def refresh_tokens(payload: RefreshRequest) -> TokenPair:
    try:
        decoded = decode_token(payload.refresh_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效") from exc
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌类型错误")
    user_id = str(decoded["sub"])
    return TokenPair(
        access_token=create_token(user_id, "access", settings.access_token_expire_minutes),
        refresh_token=create_token(user_id, "refresh", settings.refresh_token_expire_minutes),
    )


@router.post("/auth/logout", response_model=ApiMessage)
def logout(_: User = Depends(get_current_user)) -> ApiMessage:
    return ApiMessage(message="已退出登录")


@router.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return serialize_user(current_user)


@router.get("/admin/users", response_model=list[UserOut])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[UserOut]:
    return [serialize_user(user) for user in db.query(User).order_by(User.id.asc()).all()]


@router.post("/admin/users", response_model=UserOut)
def create_user(payload: UserCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> UserOut:
    user = User(
        username=payload.username,
        password_hash=build_default_password_hash(settings.default_password),
        role=payload.role,
        name=payload.name,
        email=payload.email,
        ip_address=payload.ip_address,
        is_active=True,
    )
    db.add(user)
    db.flush()
    write_audit(db, current_user.id, "CREATE_USER", "User", user.id, {}, {"username": user.username, "role": user.role})
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> UserOut:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    ensure_last_admin_not_removed(db, user, payload.role, payload.is_active)
    before = {"role": user.role, "is_active": user.is_active, "email": user.email, "ip_address": user.ip_address}
    user.role = payload.role
    user.name = payload.name
    user.email = payload.email
    user.ip_address = payload.ip_address
    user.is_active = payload.is_active
    write_audit(db, current_user.id, "UPDATE_USER", "User", user.id, before, {"role": user.role, "is_active": user.is_active})
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> DashboardSummary:
    tasks = db.query(Task).filter(Task.deleted_at.is_(None)).all()
    notifications = db.query(Notification).all()
    recipients = db.query(NotificationRecipient).all()
    email_notifications = [item for item in notifications if item.channel == "email"]
    qax_ids = {item.id for item in notifications if item.channel == "qax"}
    qax_recipients = [item for item in recipients if item.notification_id in qax_ids]
    email_success = sum(1 for item in email_notifications if item.status in ("sent", "delivered"))

    return DashboardSummary(
        task_total=len(tasks),
        in_progress_total=sum(1 for item in tasks if item.main_status == "in_progress"),
        done_total=sum(1 for item in tasks if item.main_status == "done"),
        canceled_total=sum(1 for item in tasks if item.main_status == "canceled"),
        delayed_total=sum(1 for item in tasks if item.delay_days > 0),
        email_success_rate=round(email_success * 100 / len(email_notifications), 2) if email_notifications else 0.0,
        qax_delivery_rate=round(sum(1 for item in qax_recipients if item.delivery_status == "delivered") * 100 / len(qax_recipients), 2)
        if qax_recipients
        else 0.0,
        qax_read_rate=round(sum(1 for item in qax_recipients if item.read_status == "read") * 100 / len(qax_recipients), 2)
        if qax_recipients
        else 0.0,
        retry_total=sum(item.retry_count for item in recipients),
    )


@router.post("/admin/users/{user_id}/disable", response_model=ApiMessage)
def disable_user(user_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    ensure_last_admin_not_removed(db, user, user.role, False)
    user.is_active = False
    write_audit(db, current_user.id, "DISABLE_USER", "User", user.id, {"is_active": True}, {"is_active": False})
    db.commit()
    return ApiMessage(message="用户已禁用")


@router.post("/admin/users/{user_id}/enable", response_model=ApiMessage)
def enable_user(user_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = True
    write_audit(db, current_user.id, "ENABLE_USER", "User", user.id, {"is_active": False}, {"is_active": True})
    db.commit()
    return ApiMessage(message="用户已启用")


@router.post("/admin/users/{user_id}/reset-password", response_model=ApiMessage)
def reset_password(user_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = build_default_password_hash(settings.default_password)
    write_audit(db, current_user.id, "RESET_PASSWORD", "User", user.id, {}, {"default_password_applied": True})
    db.commit()
    return ApiMessage(message="密码已重置")


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[TaskOut]:
    query = db.query(Task).filter(Task.deleted_at.is_(None))
    if current_user.role != "admin":
        task_ids = [tm.task_id for tm in db.query(TaskMember).filter(TaskMember.user_id == current_user.id).all()]
        query = query.filter(Task.id.in_(task_ids))
    return [serialize_task(task, db) for task in query.order_by(Task.id.desc()).all()]


@router.post("/tasks", response_model=TaskOut)
def create_task(payload: TaskCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> TaskOut:
    if payload.start_at > payload.end_at:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")
    inferred_status = infer_task_status_by_time(payload.start_at, payload.end_at)
    task = Task(
        title=payload.title,
        content=payload.content,
        priority=payload.priority,
        remark=payload.remark,
        start_at=payload.start_at,
        end_at=payload.end_at,
        due_remind_days=max(payload.due_remind_days, 0),
        planned_minutes=int((payload.end_at - payload.start_at).total_seconds() // 60),
        main_status=inferred_status,
        created_by=current_user.id,
    )
    db.add(task)
    db.flush()
    member_ids = {payload.owner_id, *payload.participant_ids}
    for user_id in member_ids:
        member_role = "owner" if user_id == payload.owner_id else "participant"
        db.add(TaskMember(task_id=task.id, user_id=user_id, member_role=member_role))
    for milestone in payload.milestones:
        if milestone.planned_at < payload.start_at or milestone.planned_at > payload.end_at:
            raise HTTPException(status_code=400, detail="里程碑时间必须位于任务时间范围内")
        db.add(
            TaskMilestone(
                task_id=task.id,
                name=milestone.name,
                planned_at=milestone.planned_at,
                remind_offsets=",".join(str(item) for item in milestone.remind_offsets),
                sort_order=milestone.sort_order,
            )
        )
    db.add(TaskStatusEvent(task_id=task.id, from_status="", to_status=inferred_status, source="web", remark="创建任务自动判定状态", operator_id=current_user.id))
    create_notification_with_recipients(db, task.id, "email", "task_created", "")
    create_notification_with_recipients(db, task.id, "qax", "task_created", "")
    write_audit(db, current_user.id, "CREATE_TASK", "Task", task.id, {}, {"title": task.title})
    db.commit()
    db.refresh(task)
    return serialize_task(task, db)


@router.get("/tasks/{task_id}", response_model=TaskDetailOut)
def get_task(task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> TaskDetailOut:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if current_user.role != "admin":
        membership = db.query(TaskMember).filter(TaskMember.task_id == task_id, TaskMember.user_id == current_user.id).first()
        if not membership:
            raise HTTPException(status_code=403, detail="无权访问该任务")
    members = db.query(TaskMember).filter(TaskMember.task_id == task.id).all()
    milestones = db.query(TaskMilestone).filter(TaskMilestone.task_id == task.id).order_by(TaskMilestone.sort_order.asc()).all()
    notifications = db.query(Notification).filter(Notification.task_id == task.id).order_by(Notification.id.desc()).all()
    delay_requests = db.query(DelayRequest).filter(DelayRequest.task_id == task.id).order_by(DelayRequest.id.desc()).all()
    events = db.query(TaskStatusEvent).filter(TaskStatusEvent.task_id == task.id).order_by(TaskStatusEvent.id.desc()).all()
    base = serialize_task(task, db)
    return TaskDetailOut(
        **base.model_dump(),
        members=[
            {
                "id": item.id,
                "user_id": item.user_id,
                "name": item.user.name if item.user else "",
                "email": item.user.email if item.user else "",
                "member_role": item.member_role,
                "member_role_text": MEMBER_ROLE_LABELS.get(item.member_role, item.member_role),
            }
            for item in members
        ],
        milestones=[
            {
                "id": item.id,
                "name": item.name,
                "planned_at": item.planned_at,
                "remind_offsets": [int(value) for value in item.remind_offsets.split(",") if value],
                "status": item.status,
            }
            for item in milestones
        ],
        notifications=[serialize_notification(item, db).model_dump() for item in notifications],
        delay_requests=[
            {
                "id": item.id,
                "applicant_id": item.applicant_id,
                "applicant_name": db.query(User).filter(User.id == item.applicant_id).first().name if item.applicant_id else "",
                "apply_reason": item.apply_reason,
                "approval_status": item.approval_status,
                "approval_status_text": DELAY_STATUS_LABELS.get(item.approval_status, item.approval_status),
                "original_deadline": item.original_deadline,
                "proposed_deadline": item.proposed_deadline,
                "approved_deadline": item.approved_deadline,
                "approve_remark": item.approve_remark,
                "decided_by_channel": item.decided_by_channel,
                "version": item.version,
            }
            for item in delay_requests
        ],
        events=[
            {
                "id": item.id,
                "from_status": item.from_status,
                "to_status": item.to_status,
                "from_status_text": task_status_text(item.from_status),
                "to_status_text": task_status_text(item.to_status),
                "source": item.source,
                "remark": item.remark,
                "created_at": item.created_at,
            }
            for item in events
        ],
    )


@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, payload: TaskCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> TaskOut:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    before = {"title": task.title, "end_at": task.end_at.isoformat(), "priority": task.priority}
    task.title = payload.title
    task.content = payload.content
    task.priority = payload.priority
    task.remark = payload.remark
    task.start_at = payload.start_at
    task.end_at = payload.end_at
    task.due_remind_days = max(payload.due_remind_days, 0)
    task.planned_minutes = int((payload.end_at - payload.start_at).total_seconds() // 60)
    write_audit(db, current_user.id, "UPDATE_TASK", "Task", task.id, before, {"title": task.title, "end_at": task.end_at.isoformat()})
    db.commit()
    db.refresh(task)
    return serialize_task(task, db)


@router.delete("/tasks/{task_id}", response_model=ApiMessage)
def delete_task(task_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.deleted_at = shanghai_now_naive()
    write_audit(db, current_user.id, "DELETE_TASK", "Task", task.id, {"deleted_at": None}, {"deleted_at": task.deleted_at.isoformat()})
    db.commit()
    return ApiMessage(message="任务已删除")


@router.post("/tasks/{task_id}/status", response_model=TaskOut)
def change_status(task_id: int, payload: TaskStatusUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> TaskOut:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    before = {"main_status": task.main_status}
    task.main_status = payload.main_status
    if payload.main_status == "done" and task.actual_minutes == 0:
        task.actual_minutes = int((shanghai_now_naive() - task.start_at).total_seconds() // 60)
    db.add(TaskStatusEvent(task_id=task.id, from_status=before["main_status"], to_status=task.main_status, source="web", remark=payload.remark, operator_id=current_user.id))
    write_audit(db, current_user.id, "CHANGE_TASK_STATUS", "Task", task.id, before, {"main_status": task.main_status})
    db.commit()
    db.refresh(task)
    return serialize_task(task, db)


@router.post("/tasks/{task_id}/lock", response_model=ApiMessage)
def lock_task(task_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.state_locked = True
    db.commit()
    return ApiMessage(message="任务状态已锁定")


@router.post("/tasks/{task_id}/unlock", response_model=ApiMessage)
def unlock_task(task_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.state_locked = False
    db.commit()
    return ApiMessage(message="任务状态已解锁")


@router.get("/templates", response_model=list[dict])
def list_templates(template_kind: str | None = Query(None), _: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    query = db.query(Template)
    if template_kind:
        query = query.filter(Template.template_kind == template_kind)
    return [
        {
            "id": item.id,
            "name": item.name,
            "template_kind": item.template_kind,
            "notify_type": item.notify_type,
            "notify_type_text": NOTIFICATION_TYPE_LABELS.get(item.notify_type, item.notify_type),
            "priority": item.priority,
            "version": item.version,
            "enabled": item.enabled,
            "is_default": item.is_default,
            "subject_rule": item.subject_rule,
            "body_rule": item.body_rule,
            "content": item.content,
        }
        for item in query.order_by(Template.id.desc()).all()
    ]


@router.get("/templates/options", response_model=dict)
def template_options(_: User = Depends(require_admin)) -> dict:
    return {
        "template_kind_options": [
            {"value": "MAIL_SEND", "label": "邮件发送模板"},
            {"value": "QAX_SEND", "label": "QAX 发送模板"},
            {"value": "MAIL_REPLY", "label": "邮件回复模板"},
        ],
        "notify_type_options": {
            kind: [{"value": code, "label": NOTIFICATION_TYPE_LABELS.get(code, code)} for code in codes]
            for kind, codes in TEMPLATE_NOTIFY_TYPE_OPTIONS.items()
        },
    }


def _validate_template_notify_type(template_kind: str, notify_type: str) -> None:
    allowed = TEMPLATE_NOTIFY_TYPE_OPTIONS.get(template_kind, [])
    if notify_type not in allowed:
        raise HTTPException(status_code=400, detail="通知类型与模板类型不匹配")


@router.post("/templates", response_model=dict)
def create_template(payload: TemplateCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    _validate_template_notify_type(payload.template_kind, payload.notify_type)
    template = Template(**payload.model_dump())
    db.add(template)
    db.flush()
    write_audit(db, current_user.id, "CREATE_TEMPLATE", "Template", template.id, {}, {"name": template.name})
    db.commit()
    return {"id": template.id}


@router.put("/templates/{template_id}", response_model=dict)
def update_template(template_id: int, payload: TemplateCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    _validate_template_notify_type(payload.template_kind, payload.notify_type)
    before = {"name": template.name, "version": template.version}
    for key, value in payload.model_dump().items():
        setattr(template, key, value)
    write_audit(db, current_user.id, "UPDATE_TEMPLATE", "Template", template.id, before, {"name": template.name, "version": template.version})
    db.commit()
    return {"id": template.id}


@router.post("/templates/{template_id}/set-default", response_model=ApiMessage)
def set_default_template(template_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    db.query(Template).filter(
        Template.template_kind == template.template_kind,
        Template.notify_type == template.notify_type,
        Template.is_default.is_(True),
    ).update({"is_default": False})
    template.is_default = True
    write_audit(db, current_user.id, "SET_TEMPLATE_DEFAULT", "Template", template.id, {}, {"is_default": True})
    db.commit()
    return ApiMessage(message="模板默认项已更新")


@router.post("/templates/preview-match", response_model=dict)
def preview_match(payload: TemplatePreviewRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    candidates = [
        item for item in sort_templates(db.query(Template).filter(Template.template_kind == payload.template_kind, Template.enabled.is_(True)).all())
        if template_matches(item, payload.subject, payload.body)
    ]
    return {
        "matches": [{"id": item.id, "name": item.name, "version": item.version, "priority": item.priority} for item in candidates],
        "selected": candidates[0].id if candidates else None,
    }


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[NotificationOut]:
    query = db.query(Notification)
    if current_user.role != "admin":
        task_ids = [tm.task_id for tm in db.query(TaskMember).filter(TaskMember.user_id == current_user.id).all()]
        query = query.filter(Notification.task_id.in_(task_ids))
    return [serialize_notification(item, db) for item in query.order_by(Notification.id.desc()).all()]


@router.get("/admin/mail/events", response_model=list[MailEventOut])
def list_mail_events(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[MailEventOut]:
    return [serialize_mail_event(item, db) for item in db.query(MailEvent).order_by(MailEvent.id.desc()).limit(100).all()]


@router.post("/admin/mail/test", response_model=dict)
def test_mail_settings(_: User = Depends(require_admin)) -> dict:
    return diagnose_mail_settings()


@router.post("/admin/mail/inbox-test", response_model=dict)
def test_mail_inbox(_: User = Depends(require_admin)) -> dict:
    return diagnose_imap_settings()


@router.post("/admin/mail/poll", response_model=dict)
def poll_mail_inbox(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return poll_mailbox(db)


@router.post("/admin/mail/baseline", response_model=dict)
def reset_mail_baseline(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return initialize_mail_scan_baseline(db)


@router.post("/tasks/{task_id}/remind", response_model=ApiMessage)
def remind_task(task_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    create_notification_with_recipients(db, task.id, "email", "manual_remind", "")
    create_notification_with_recipients(db, task.id, "qax", "manual_remind", "")
    write_audit(db, current_user.id, "REMIND_TASK", "Task", task.id, {}, {"notification_created": True})
    db.commit()
    return ApiMessage(message="已创建提醒通知")


@router.post("/tasks/due-remind/run", response_model=ApiMessage)
def run_due_remind(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> ApiMessage:
    count = create_due_reminders(db)
    db.commit()
    return ApiMessage(message=f"已创建 {count} 条到期提醒通知")


@router.post("/delay-requests", response_model=dict)
def create_delay_request(payload: DelayRequestCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    task = db.query(Task).filter(Task.id == payload.task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    request_obj = DelayRequest(
        task_id=task.id,
        applicant_id=current_user.id,
        apply_reason=payload.apply_reason,
        original_deadline=task.end_at,
        proposed_deadline=payload.proposed_deadline,
    )
    db.add(request_obj)
    db.flush()
    admin_ids = [item.id for item in db.query(User).filter(User.role == "admin", User.is_active.is_(True)).all()]
    extra_context = {
        "delay_request_id": request_obj.id,
        "applicant_name": current_user.name,
        "proposed_deadline": payload.proposed_deadline.strftime("%Y-%m-%d"),
        "apply_reason": payload.apply_reason,
    }
    create_notification_with_recipients(db, task.id, "email", "delay_approval", "", recipient_user_ids=admin_ids, extra_context=extra_context)
    create_notification_with_recipients(db, task.id, "qax", "delay_approval", "", recipient_user_ids=admin_ids, extra_context=extra_context)
    write_audit(db, current_user.id, "CREATE_DELAY_REQUEST", "DelayRequest", request_obj.id, {}, {"task_id": task.id})
    db.commit()
    return {"id": request_obj.id}


@router.get("/delay-requests/pending", response_model=list[dict])
def list_pending_delay_requests(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    result = []
    for item in db.query(DelayRequest).order_by(DelayRequest.id.desc()).all():
        task = db.query(Task).filter(Task.id == item.task_id).first()
        applicant = db.query(User).filter(User.id == item.applicant_id).first()
        result.append(
            {
                "id": item.id,
                "task_id": item.task_id,
                "task_title": task.title if task else "",
                "applicant_id": item.applicant_id,
                "applicant_name": applicant.name if applicant else "",
                "approval_status": item.approval_status,
                "approval_status_text": DELAY_STATUS_LABELS.get(item.approval_status, item.approval_status),
                "apply_reason": item.apply_reason,
                "original_deadline": item.original_deadline,
                "proposed_deadline": item.proposed_deadline,
                "approved_deadline": item.approved_deadline,
                "approve_remark": item.approve_remark,
                "decided_by_channel": item.decided_by_channel,
                "version": item.version,
            }
        )
    return result


@router.post("/delay-requests/{delay_id}/approve", response_model=dict)
def decide_delay_request(delay_id: int, payload: DelayDecisionRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    request_obj = db.query(DelayRequest).filter(DelayRequest.id == delay_id).first()
    if not request_obj:
        raise HTTPException(status_code=404, detail="延期申请不存在")
    result, updated = apply_delay_decision(
        db=db,
        request_obj=request_obj,
        admin_id=current_user.id,
        request_id=payload.request_id,
        action=payload.action,
        channel="web",
        version=payload.version,
        remark=payload.remark,
        approved_deadline=payload.approved_deadline,
    )
    db.commit()
    return {
        "status": result,
        "status_text": DELAY_STATUS_LABELS.get(updated.approval_status, updated.approval_status),
        "id": updated.id,
        "approval_status": updated.approval_status,
    }


@router.get("/tasks/import-template")
def task_import_template(_: User = Depends(require_admin)) -> StreamingResponse:
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["title", "content", "owner_username", "participant_usernames", "start_at", "end_at", "priority", "remark", "milestone_names", "milestone_datetimes", "remind_offsets"])
    writer.writerow(["月度汇总", "完成月度汇总整理", "admin", "member1,member2", "2026-04-21T09:00:00", "2026-04-30T18:00:00", "high", "内部演示", "初稿|复核", "2026-04-24T10:00:00|2026-04-28T10:00:00", "1,3|1,2,5"])
    return StreamingResponse(iter([csv_buffer.getvalue().encode("utf-8")]), media_type="text/csv")


@router.post("/tasks/import", response_model=ApiMessage)
def import_tasks(_: User = Depends(require_admin)) -> ApiMessage:
    return ApiMessage(message="导入接口骨架已就位，解析流程将在下一阶段接入")


@router.get("/reports/export")
def export_report(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["task_id", "title", "status", "delay_days"])
    for task in db.query(Task).filter(Task.deleted_at.is_(None)).order_by(Task.id.asc()).all():
        writer.writerow([task.id, task.title, task.main_status, task.delay_days])
    return StreamingResponse(iter([csv_buffer.getvalue().encode("utf-8")]), media_type="text/csv")


@router.get("/audit-logs", response_model=list[AuditOut])
def list_audit_logs(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[AuditOut]:
    return [
        AuditOut(id=item.id, action_type=item.action_type, target_type=item.target_type, target_id=item.target_id, created_at=item.created_at)
        for item in db.query(AuditLog).order_by(AuditLog.id.desc()).all()
    ]
