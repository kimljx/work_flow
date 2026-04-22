from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Notification, NotificationRecipient, Task, TaskMember, Template, User
from app.services.mail import send_mail_notification
from app.timeutils import shanghai_now_naive


def _render_template(content: str, context: dict[str, str]) -> str:
    rendered = content
    for key, value in context.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered


def _build_context(task: Task | None, extra_context: dict[str, str] | None = None) -> dict[str, str]:
    context = {
        "task_id": task.id if task else "",
        "task_title": task.title if task else "",
        "task_content": task.content if task else "",
        "start_at": task.start_at.strftime("%Y-%m-%d %H:%M") if task else "",
        "end_at": task.end_at.strftime("%Y-%m-%d %H:%M") if task else "",
        "reply_guide": "请按“任务ID + 状态关键词 + 可选说明内容 + 日期 + 原因”回复",
    }
    if extra_context:
        context.update({key: "" if value is None else str(value) for key, value in extra_context.items()})
    return context


def _default_subject(task: Task | None, notify_type: str, extra_context: dict[str, str] | None = None) -> str:
    if notify_type == "delay_approval":
        delay_request_id = extra_context.get("delay_request_id") if extra_context else ""
        title = task.title if task else "未知任务"
        return f"延期审批待处理通知#{delay_request_id}：{title}"
    if task:
        return f"任务通知提醒#{task.id}：{task.title}"
    return f"系统通知：{notify_type}"


def _default_content(task: Task | None, notify_type: str, extra_context: dict[str, str] | None = None) -> str:
    context = _build_context(task, extra_context)
    if notify_type == "delay_approval":
        return (
            f"延期申请ID：{context.get('delay_request_id', '')}\n"
            f"任务ID：{context.get('task_id', '')}\n"
            f"任务标题：{context.get('task_title', '')}\n"
            f"申请人：{context.get('applicant_name', '')}\n"
            f"申请截止日期：{context.get('proposed_deadline', '')}\n"
            f"申请原因：{context.get('apply_reason', '')}\n"
            "请直接回复“延期申请ID + 同意 / 拒绝 + 日期”"
        )
    return (
        f"任务ID：{context.get('task_id', '')}\n"
        f"任务标题：{context.get('task_title', '')}\n"
        f"开始时间：{context.get('start_at', '')}\n"
        f"结束时间：{context.get('end_at', '')}\n"
        f"{context.get('reply_guide', '')}"
    )


def _resolve_template_content(db: Session, channel: str, notify_type: str, task: Task | None, extra_context: dict[str, str] | None = None) -> tuple[str, str]:
    template_kind = "MAIL_SEND" if channel == "email" else "QAX_SEND"
    template = (
        db.query(Template)
        .filter(Template.template_kind == template_kind, Template.notify_type == notify_type, Template.is_default.is_(True))
        .order_by(Template.version.desc(), Template.id.asc())
        .first()
    )
    subject = _default_subject(task, notify_type, extra_context)
    content = _default_content(task, notify_type, extra_context)
    if template:
        content = _render_template(template.content, _build_context(task, extra_context))
    return subject, content


def create_notification_with_recipients(
    db: Session,
    task_id: int,
    channel: str,
    notify_type: str,
    content_snapshot: str,
    recipient_user_ids: list[int] | None = None,
    extra_context: dict[str, str] | None = None,
) -> Notification:
    task = db.query(Task).filter(Task.id == task_id).first()
    subject, rendered_content = _resolve_template_content(db, channel, notify_type, task, extra_context)
    notification = Notification(
        task_id=task_id,
        channel=channel,
        notify_type=notify_type,
        content_snapshot=content_snapshot or rendered_content,
        status="pending",
    )
    db.add(notification)
    db.flush()

    success_count = 0
    failure_count = 0
    if recipient_user_ids is None:
        members = db.query(TaskMember).filter(TaskMember.task_id == task_id).all()
        recipient_specs = [(item.user_id, item.member_role) for item in members]
    else:
        recipient_specs = [(user_id, "admin") for user_id in recipient_user_ids]

    seen_users: set[int] = set()
    for user_id, recipient_role in recipient_specs:
        if user_id in seen_users:
            continue
        seen_users.add(user_id)
        user = db.query(User).filter(User.id == user_id).first()
        delivery_status = "pending"
        read_status = "unread"
        last_error = ""

        if channel == "email":
            result = send_mail_notification(
                to_address=user.email if user else "",
                subject=subject,
                content=content_snapshot or rendered_content,
            )
            if result["status"] == "sent":
                delivery_status = "delivered"
                success_count += 1
            else:
                delivery_status = "failed"
                last_error = result["message"]
                failure_count += 1

        db.add(
            NotificationRecipient(
                notification_id=notification.id,
                user_id=user_id,
                recipient_role=recipient_role,
                delivery_status=delivery_status,
                read_status=read_status,
                last_error=last_error,
            )
        )

    if channel == "email":
        if success_count == 0 and failure_count > 0:
            notification.status = "failed"
        elif success_count > 0:
            notification.status = "delivered"
        else:
            notification.status = "pending"
    else:
        notification.status = "pending"

    return notification


def create_due_reminders(db: Session) -> int:
    now = shanghai_now_naive()
    created = 0
    tasks = db.query(Task).filter(Task.deleted_at.is_(None), Task.due_remind_days > 0).all()
    for task in tasks:
        days_left = (task.end_at.date() - now.date()).days
        if days_left != task.due_remind_days:
            continue

        exists = (
            db.query(Notification)
            .filter(
                Notification.task_id == task.id,
                Notification.notify_type == "due_remind",
                Notification.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
                Notification.created_at <= now.replace(hour=23, minute=59, second=59, microsecond=999999),
            )
            .first()
        )
        if exists:
            continue

        create_notification_with_recipients(db, task.id, "email", "due_remind", "")
        create_notification_with_recipients(db, task.id, "qax", "due_remind", "")
        created += 1
    return created
