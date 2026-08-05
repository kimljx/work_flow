from __future__ import annotations

"""通知生成与渲染服务。"""

from sqlalchemy.orm import Session

from app.models import Notification, NotificationRecipient, Task, TaskMember, TaskSubtask, Template, User
from app.services.mail import send_mail_notification
from app.services.qax import sanitize_qax_content, send_qax_notification
from app.timeutils import shanghai_now_naive


REPLY_GUIDE = "回复指引：\n1. 回复“进行中 + 说明”可更新任务状态。\n2. 回复“已完成 + 说明”可将任务标记为完成。"


def _render_template(content: str, context: dict[str, str]) -> str:
    """用上下文变量渲染模板正文。"""
    rendered = content
    for key, value in context.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    return rendered


def _select_default_template(db: Session, channel: str, notify_type: str) -> Template | None:
    """按渠道与通知类型读取当前启用的默认模板。"""
    template_kind = "MAIL_SEND" if channel == "email" else "QAX_SEND"
    return (
        db.query(Template)
        .filter(
            Template.template_kind == template_kind,
            Template.notify_type == notify_type,
            Template.enabled.is_(True),
            Template.is_default.is_(True),
        )
        .order_by(Template.version.desc(), Template.id.asc())
        .first()
    )


def _owner_and_creator_names(task: Task | None, db: Session) -> tuple[str, str]:
    """提取负责人和任务创建人姓名。"""
    if not task:
        return "", ""
    # 当前会话默认关闭 autoflush，创建任务后要先手动 flush，才能在同一事务里查到刚写入的成员与子任务。
    db.flush()

    owner_name = ""
    owner_member = (
        db.query(TaskMember)
        .filter(TaskMember.task_id == task.id, TaskMember.member_role == "owner")
        .order_by(TaskMember.id.asc())
        .first()
    )
    if owner_member and owner_member.user:
        owner_name = owner_member.user.name

    creator_name = ""
    if task.created_by:
        # 任务创建人必须按 created_by 直接查询用户，不能再从成员表里反推。
        creator = db.query(User).filter(User.id == task.created_by).first()
        creator_name = creator.name if creator else ""
    if not creator_name:
        creator_name = owner_name
    return owner_name, creator_name


def _task_subtasks(db: Session, task: Task | None, recipient: User | None = None) -> list[TaskSubtask]:
    """按任务和接收人读取子任务列表，避免关系缓存导致的空结果。"""
    if not task:
        return []
    db.flush()
    query = db.query(TaskSubtask).filter(TaskSubtask.task_id == task.id).order_by(TaskSubtask.sort_order.asc(), TaskSubtask.id.asc())
    if recipient is not None:
        query = query.filter(TaskSubtask.assignee_id == recipient.id)
    return query.all()


def _build_context(
    db: Session,
    task: Task | None,
    recipient: User | None = None,
    extra_context: dict[str, str] | None = None,
) -> dict[str, str]:
    """构建模板渲染上下文，并按接收人过滤子任务。"""
    owner_name, creator_name = _owner_and_creator_names(task, db)
    subtasks = _task_subtasks(db, task, recipient=recipient)

    subtask_lines: list[str] = []
    for index, item in enumerate(subtasks, start=1):
        assignee_name = item.assignee.name if item.assignee else f"成员#{item.assignee_id}"
        summary = f"{index}. {item.title}（执行人：{assignee_name}）"
        if item.content:
            summary = f"{summary}：{item.content}"
        subtask_lines.append(summary)

    empty_text = "当前接收人暂未分配子任务" if recipient is not None else "暂无子任务"
    context = {
        "task_id": task.id if task else "",
        "task_title": task.title if task else "",
        "task_content": task.content if task else "",
        "task_remark": task.remark if task else "",
        "start_at": task.start_at.strftime("%Y-%m-%d %H:%M") if task else "",
        "end_at": task.end_at.strftime("%Y-%m-%d %H:%M") if task else "",
        "owner_name": owner_name,
        "creator_name": creator_name,
        "recipient_name": recipient.name if recipient else "",
        "subtask_summary": "\n".join(subtask_lines) if subtask_lines else empty_text,
        "subtask_brief": "；".join(subtask_lines[:3]) if subtask_lines else empty_text,
        "remind_focus": "主任务整体进度跟进",
        "reply_guide": "请按“任务ID + 状态关键词 + 可选说明内容 / 日期 / 原因”回复。",
    }
    context["reply_guide"] = REPLY_GUIDE
    if extra_context:
        context.update({key: "" if value is None else str(value) for key, value in extra_context.items()})
    return context


def _default_subject(task: Task | None, notify_type: str, extra_context: dict[str, str] | None = None) -> str:
    """在没有模板标题时生成默认主题。"""
    if notify_type == "delay_approval":
        delay_request_id = extra_context.get("delay_request_id") if extra_context else ""
        title = task.title if task else "未知任务"
        return f"延期审批待处理通知#{delay_request_id}：{title}"
    if task:
        if notify_type == "task_updated":
            return f"【任务通知#{task.id}】（更新）{task.title}"
        return f"【任务通知#{task.id}】{task.title}"
    return f"系统通知：{notify_type}"


def _remove_deprecated_template_lines(content: str) -> str:
    lines = []
    for line in (content or "").splitlines():
        if "{task_remark}" in line or "主任务备注" in line:
            continue
        if "延期" in line or "同意" in line or "拒绝" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _default_content(
    db: Session,
    task: Task | None,
    notify_type: str,
    recipient: User | None = None,
    extra_context: dict[str, str] | None = None,
) -> str:
    """在没有模板正文时生成默认通知内容。"""
    context = _build_context(db, task, recipient=recipient, extra_context=extra_context)
    if notify_type == "delay_approval":
        return (
            f"延期申请ID：{context.get('delay_request_id', '')}\n"
            f"任务ID：{context.get('task_id', '')}\n"
            f"任务标题：{context.get('task_title', '')}\n"
            f"负责人：{context.get('owner_name', '')}\n"
            f"任务创建人：{context.get('creator_name', '')}\n"
            f"申请人：{context.get('applicant_name', '')}\n"
            f"申请截止日期：{context.get('proposed_deadline', '')}\n"
            f"申请原因：{context.get('apply_reason', '')}\n"
            "请直接回复“延期申请ID + 同意 / 拒绝 + 日期”。"
        )
    if notify_type == "task_updated":
        update_summary = context.get("update_summary") or context.get("remind_focus") or "任务内容已更新，请查看最新安排。"
        return (
            f"任务更新提示：{update_summary}\n"
            f"任务ID：{context.get('task_id', '')}\n"
            f"任务标题：{context.get('task_title', '')}\n"
            f"负责人：{context.get('owner_name', '')}\n"
            f"任务创建人：{context.get('creator_name', '')}\n"
            f"开始时间：{context.get('start_at', '')}\n"
            f"结束时间：{context.get('end_at', '')}\n"
            f"主任务详情：{context.get('task_content', '') or '暂无'}\n"
            f"主任务备注：{context.get('task_remark', '') or '暂无'}\n"
            f"子任务安排：\n{context.get('subtask_summary', '暂无子任务')}\n"
            f"{context.get('reply_guide', '')}"
        )
    return (
        f"任务ID：{context.get('task_id', '')}\n"
        f"任务标题：{context.get('task_title', '')}\n"
        f"负责人：{context.get('owner_name', '')}\n"
        f"任务创建人：{context.get('creator_name', '')}\n"
        f"开始时间：{context.get('start_at', '')}\n"
        f"结束时间：{context.get('end_at', '')}\n"
        f"主任务详情：{context.get('task_content', '') or '暂无'}\n"
        f"主任务备注：{context.get('task_remark', '') or '暂无'}\n"
        f"当前提醒重点：{context.get('remind_focus', '') or '主任务整体进度跟进'}\n"
        f"子任务安排：\n{context.get('subtask_summary', '暂无子任务')}\n"
        f"{context.get('reply_guide', '')}"
    )


def _resolve_template_payload(
    db: Session,
    channel: str,
    notify_type: str,
    task: Task | None,
    recipient: User | None = None,
    extra_context: dict[str, str] | None = None,
) -> tuple[Template | None, dict[str, str], str, str]:
    """统一解析模板、渲染上下文与最终正文。"""
    template = _select_default_template(db, channel, notify_type)
    context = _build_context(db, task, recipient=recipient, extra_context=extra_context)
    subject = _default_subject(task, notify_type, extra_context)
    content = _default_content(db, task, notify_type, recipient=recipient, extra_context=extra_context)
    content = _remove_deprecated_template_lines(content)
    if template:
        cleaned_template_content = _remove_deprecated_template_lines(template.content)
        if cleaned_template_content:
            content = _render_template(cleaned_template_content, context)
        if task and _task_subtasks(db, task) and "{subtask_" not in template.content and "子任务" not in content:
            # 老模板如果没显式带子任务变量，这里自动补一段，避免成员收到缺少拆分任务信息的正文。
            content = f"{content}\n子任务安排：\n{context.get('subtask_summary', '暂无子任务')}"
    return template, context, subject, content


def _resolve_template_content(
    db: Session,
    channel: str,
    notify_type: str,
    task: Task | None,
    recipient: User | None = None,
    extra_context: dict[str, str] | None = None,
) -> tuple[str, str]:
    """解析指定渠道与通知类型最终应发送的主题和正文。"""
    _, _, subject, content = _resolve_template_payload(
        db,
        channel,
        notify_type,
        task,
        recipient=recipient,
        extra_context=extra_context,
    )
    return subject, content


def _normalize_outbound_content(channel: str, content: str) -> str:
    """按渠道清洗最终发送正文。

    邮件保留原始换行与回复指引；QAX 会移除邮件专属回复说明，
    保证通知详情页展示的快照与接收人实际看到的即时消息正文一致。
    """

    if channel == "qax":
        return sanitize_qax_content(content)
    return content


def preview_notification_content(
    db: Session,
    task: Task | None,
    channel: str,
    notify_type: str,
    recipient: User | None = None,
    extra_context: dict[str, str] | None = None,
) -> dict[str, object]:
    """返回通知最终渲染结果，供任务详情页直接预览。"""
    template, context, subject, content = _resolve_template_payload(
        db,
        channel,
        notify_type,
        task,
        recipient=recipient,
        extra_context=extra_context,
    )
    return {
        "template_name": template.name if template else "系统默认正文",
        "template_version": template.version if template else None,
        "subject": subject,
        "content": content,
        "context": context,
    }


def create_notification_with_recipients(
    db: Session,
    task_id: int,
    channel: str,
    notify_type: str,
    content_snapshot: str,
    recipient_user_ids: list[int] | None = None,
    extra_context: dict[str, str] | None = None,
) -> Notification:
    """创建通知及其接收人记录。"""
    task = db.query(Task).filter(Task.id == task_id).first()
    _, _, _, rendered_content = _resolve_template_payload(db, channel, notify_type, task, extra_context=extra_context)
    default_snapshot = _normalize_outbound_content(channel, content_snapshot or rendered_content)
    _, creator_name = _owner_and_creator_names(task, db)
    notification = Notification(
        task_id=task_id,
        channel=channel,
        notify_type=notify_type,
        content_snapshot=default_snapshot,
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
        subject, personalized_content = _resolve_template_content(
            db,
            channel,
            notify_type,
            task,
            recipient=user,
            extra_context=extra_context,
        )
        outbound_content = _normalize_outbound_content(channel, content_snapshot or personalized_content)
        delivery_status = "pending"
        read_status = "unread"
        last_error = ""

        if channel == "email":
            result = send_mail_notification(
                to_address=user.email if user else "",
                subject=subject,
                content=outbound_content,
            )
            if result["status"] == "sent":
                delivery_status = "delivered"
                success_count += 1
            else:
                delivery_status = "failed"
                last_error = result["message"]
                failure_count += 1
        elif channel == "qax":
            recipient_row = NotificationRecipient(
                notification_id=notification.id,
                user_id=user_id,
                recipient_role=recipient_role,
                delivery_status=delivery_status,
                read_status=read_status,
                retry_count=0,
                content_snapshot=outbound_content,
                last_error=last_error,
            )
            db.add(recipient_row)
            db.flush()
            result = send_qax_notification(
                notification=notification,
                recipient=recipient_row,
                task=task,
                user=user,
                subject=subject,
                content=outbound_content,
                publisher_name=creator_name,
            )
            if result["status"] != "queued":
                delivery_status = "failed"
                last_error = result["message"]
                failure_count += 1
            recipient_row.delivery_status = delivery_status
            recipient_row.last_error = last_error
            continue

        db.add(
            NotificationRecipient(
                notification_id=notification.id,
                user_id=user_id,
                recipient_role=recipient_role,
                delivery_status=delivery_status,
                read_status=read_status,
                retry_count=0,
                content_snapshot=outbound_content,
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
    elif channel == "qax":
        notification.status = "failed" if success_count == 0 and failure_count > 0 else "pending"
    else:
        notification.status = "pending"

    return notification


def create_due_reminders(db: Session) -> int:
    """批量创建到期提醒通知。"""
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
            # 同一天同一任务只生成一次到期提醒，避免重复打扰成员。
            continue

        create_notification_with_recipients(db, task.id, "email", "due_remind", "")
        create_notification_with_recipients(db, task.id, "qax", "due_remind", "")
        created += 1
    return created


def create_overdue_task_reminders(db: Session) -> int:
    """为延期或已过截止时间但未完成的主任务每天生成一次提醒。"""
    now = shanghai_now_naive()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    created = 0
    tasks = (
        db.query(Task)
        .filter(
            Task.deleted_at.is_(None),
            Task.main_status.notin_(["done", "canceled"]),
        )
        .all()
    )
    for task in tasks:
        overdue_days = max((now.date() - task.end_at.date()).days, 0)
        if task.delay_days <= 0 and overdue_days <= 0:
            continue
        exists = (
            db.query(Notification)
            .filter(
                Notification.task_id == task.id,
                Notification.notify_type == "manual_remind",
                Notification.created_at >= day_start,
                Notification.created_at <= day_end,
                Notification.content_snapshot.like("%延期任务提醒%"),
            )
            .first()
        )
        if exists:
            continue
        delay_text = f"已延期 {task.delay_days} 天" if task.delay_days > 0 else f"已超过截止时间 {overdue_days} 天"
        focus = f"延期任务提醒：{delay_text}，请尽快反馈进展或完成任务。"
        create_notification_with_recipients(db, task.id, "email", "manual_remind", "", extra_context={"remind_focus": focus})
        create_notification_with_recipients(db, task.id, "qax", "manual_remind", "", extra_context={"remind_focus": focus})
        created += 1
    return created
