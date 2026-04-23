from __future__ import annotations

"""数据库初始化与默认数据灌入。"""

from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Template, User
from app.security import hash_password


DEFAULT_TEMPLATES = [
    {
        "name": "默认邮件发送模板",
        "template_kind": "MAIL_SEND",
        "notify_type": "task_created",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "您好，{recipient_name}。\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n开始时间：{start_at}\n结束时间：{end_at}\n子任务安排：\n{subtask_summary}\n\n回复指引：\n1. 回复“进行中 + 备注”可更新任务状态。\n2. 回复“已完成 + 备注”可将任务标记为完成。\n3. 如需延期，请回复“延期 + 新日期 + 原因”。",
    },
    {
        "name": "默认邮件提醒模板",
        "template_kind": "MAIL_SEND",
        "notify_type": "manual_remind",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "任务提醒：\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n子任务安排：\n{subtask_summary}\n请尽快处理并按模板回复邮件反馈状态。",
    },
    {
        "name": "默认延期审批邮件模板",
        "template_kind": "MAIL_SEND",
        "notify_type": "delay_approval",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "收到新的延期申请，请管理员处理。\n任务创建人：{creator_name}\n负责人：{owner_name}\n延期申请编号：{delay_request_id}\n任务编号：{task_id}\n任务名称：{task_title}\n申请人：{applicant_name}\n申请延期到：{proposed_deadline}\n原因：{apply_reason}\n\n可在系统中审批，也可邮件回复：\n同意 + 新日期\n或\n拒绝 + 原因",
    },
    {
        "name": "默认到期提醒邮件模板",
        "template_kind": "MAIL_SEND",
        "notify_type": "due_remind",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "任务到期提醒：\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n结束时间：{end_at}\n子任务安排：\n{subtask_summary}\n请尽快处理。",
    },
    {
        "name": "默认即时消息发送模板",
        "template_kind": "QAX_SEND",
        "notify_type": "task_created",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "您好，{recipient_name}。任务创建人：{creator_name}，负责人：{owner_name}。您有新的任务通知，任务编号：{task_id}，任务名称：{task_title}，子任务：{subtask_brief}",
    },
    {
        "name": "默认即时消息提醒模板",
        "template_kind": "QAX_SEND",
        "notify_type": "manual_remind",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "任务提醒：{task_title}（任务编号：{task_id}），任务创建人：{creator_name}，负责人：{owner_name}，子任务：{subtask_brief}，请尽快处理。",
    },
    {
        "name": "默认延期审批即时消息模板",
        "template_kind": "QAX_SEND",
        "notify_type": "delay_approval",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "新的延期审批待处理：延期申请编号 {delay_request_id}，任务 {task_title}。",
    },
    {
        "name": "默认到期提醒即时消息模板",
        "template_kind": "QAX_SEND",
        "notify_type": "due_remind",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "任务“{task_title}”即将到期（{end_at}），负责人：{owner_name}，子任务：{subtask_brief}。",
    },
    {
        "name": "回复模板-已完成",
        "template_kind": "MAIL_REPLY",
        "notify_type": "task_done",
        "priority": 120,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "已完成|完成",
        "body_rule": "已完成|完成",
        "content": "用于识别任务完成回复。",
    },
    {
        "name": "回复模板-进行中",
        "template_kind": "MAIL_REPLY",
        "notify_type": "task_in_progress",
        "priority": 110,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "进行中|处理中",
        "body_rule": "进行中|处理中",
        "content": "用于识别任务进行中回复。",
    },
    {
        "name": "回复模板-延期申请",
        "template_kind": "MAIL_REPLY",
        "notify_type": "delay_request",
        "priority": 130,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "延期",
        "body_rule": "延期",
        "content": "用于识别成员延期申请。格式：延期 + 新日期 + 原因。",
    },
    {
        "name": "回复模板-延期审批",
        "template_kind": "MAIL_REPLY",
        "notify_type": "delay_approve",
        "priority": 140,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "同意|拒绝",
        "body_rule": "同意|拒绝",
        "content": "用于识别管理员延期审批。格式：同意 + 新日期 或 拒绝 + 原因。",
    },
]


def _ensure_schema_columns() -> None:
    """在 SQLite 场景下补齐历史库缺失字段。"""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        task_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}
        if "due_remind_days" not in task_columns:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN due_remind_days INTEGER NOT NULL DEFAULT 0"))
        recipient_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(notification_recipients)")).fetchall()}
        if "content_snapshot" not in recipient_columns:
            conn.execute(text("ALTER TABLE notification_recipients ADD COLUMN content_snapshot TEXT NOT NULL DEFAULT ''"))


def bootstrap_database() -> None:
    """初始化数据库、默认账号与默认模板。"""
    if settings.database_url.startswith("sqlite:///./"):
        db_path = Path(settings.database_url.replace("sqlite:///./", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _ensure_schema_columns()
    with SessionLocal() as db:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(
                        username="admin",
                        password_hash=hash_password(settings.default_password),
                        role="admin",
                        name="系统管理员",
                        email="admin@example.com",
                        ip_address="10.0.0.1",
                        is_active=True,
                    ),
                    User(
                        username="member",
                        password_hash=hash_password(settings.default_password),
                        role="member",
                        name="默认成员",
                        email="member@example.com",
                        ip_address="10.0.0.2",
                        is_active=True,
                    ),
                ]
            )
            db.commit()

        existing_keys = {(item.template_kind, item.notify_type, item.name) for item in db.query(Template).all()}
        for template_data in DEFAULT_TEMPLATES:
            key = (template_data["template_kind"], template_data["notify_type"], template_data["name"])
            if key in existing_keys:
                continue
            # 仅补齐缺失模板，避免覆盖管理员在线调整过的模板内容。
            db.add(Template(**template_data))
        db.commit()
