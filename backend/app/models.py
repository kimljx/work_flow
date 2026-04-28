from __future__ import annotations

"""SQLAlchemy 数据模型定义。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.timeutils import shanghai_now_naive


class TimestampMixin:
    """为业务表提供统一的创建时间字段。"""
    created_at: Mapped[datetime] = mapped_column(DateTime, default=shanghai_now_naive, nullable=False)


class User(Base, TimestampMixin):
    """系统用户表，兼顾管理员与普通成员。"""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    ip_address: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Task(Base, TimestampMixin):
    """任务主表，记录任务时间范围、状态与提醒配置。"""
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    main_status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started")
    delay_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    due_remind_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    members = relationship("TaskMember", back_populates="task", cascade="all, delete-orphan")
    milestones = relationship("TaskMilestone", back_populates="task", cascade="all, delete-orphan")
    subtasks = relationship("TaskSubtask", back_populates="task", cascade="all, delete-orphan")


class TaskMember(Base, TimestampMixin):
    """任务成员关联表，区分负责人和参与人。"""
    __tablename__ = "task_members"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_task_user"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    member_role: Mapped[str] = mapped_column(String(16), nullable=False)

    task = relationship("Task", back_populates="members")
    user = relationship("User")


class TaskMilestone(Base, TimestampMixin):
    """任务里程碑表，用于细化关键节点与提醒偏移量。"""
    __tablename__ = "task_milestones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    planned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    remind_offsets: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    task = relationship("Task", back_populates="milestones")


class TaskSubtask(Base, TimestampMixin):
    """任务子任务表，记录主任务下拆分给成员的执行项。"""
    __tablename__ = "task_subtasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    task = relationship("Task", back_populates="subtasks")
    assignee = relationship("User")


class TaskStatusEvent(Base, TimestampMixin):
    """任务状态变更流水，用于详情页与审计回溯。"""
    __tablename__ = "task_status_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    from_status: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Template(Base, TimestampMixin):
    """通知模板表，覆盖邮件发送、即时消息发送与邮件回复识别。"""
    __tablename__ = "templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    template_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    notify_type: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subject_rule: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_rule: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Notification(Base, TimestampMixin):
    """通知主表，记录一次通知发送的快照与整体状态。"""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    notify_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")


class NotificationRecipient(Base, TimestampMixin):
    """通知接收人表，按成员拆分送达、回复与重试情况。"""
    __tablename__ = "notification_recipients"
    __table_args__ = (UniqueConstraint("notification_id", "user_id", name="uq_notification_recipient"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recipient_role: Mapped[str] = mapped_column(String(16), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    read_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unread")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_error: Mapped[str] = mapped_column(Text, nullable=False, default="")


class TaskImportHistory(Base, TimestampMixin):
    """任务导入批次表，记录导入结果、重复风险与行签名。"""
    __tablename__ = "task_import_histories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overlap_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    row_signatures_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    operator = relationship("User")


class DelayRequest(Base, TimestampMixin):
    """延期申请主表，保存审批状态、版本号与审批结果。"""
    __tablename__ = "delay_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    apply_reason: Mapped[str] = mapped_column(Text, nullable=False)
    original_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    proposed_deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approve_remark: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision_token: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    decided_by_channel: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DelayRequestEvent(Base, TimestampMixin):
    """延期审批事件流，记录幂等键与原始处理载荷。"""
    __tablename__ = "delay_request_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("delay_requests.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="")


class MailEvent(Base, TimestampMixin):
    """收件事件表，记录进入系统的原始邮件及其模板匹配结果。"""
    __tablename__ = "mail_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    from_addr: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body_digest: Mapped[str] = mapped_column(Text, nullable=False)
    original_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resolved_template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"), nullable=True)
    resolved_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")


class MailAction(Base, TimestampMixin):
    """邮件动作表，描述某封邮件最终触发的业务动作及结果。"""
    __tablename__ = "mail_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mail_event_id: Mapped[int] = mapped_column(ForeignKey("mail_events.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    action_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    action_result_json: Mapped[str] = mapped_column(Text, nullable=False, default="")


class MailScanState(Base):
    """邮箱扫描状态表，记录基线与最近拉取时间。"""
    __tablename__ = "mail_scan_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    baseline_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base, TimestampMixin):
    """审计日志表，记录关键管理动作的前后状态。"""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    after_json: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
