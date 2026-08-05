from __future__ import annotations

"""数据库初始化与默认数据灌入。"""

from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import MailAction, MailEvent, Template, User
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
        "content": "您好，{recipient_name}。\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n开始时间：{start_at}\n结束时间：{end_at}\n主任务详情：{task_content}\n主任务备注：{task_remark}\n当前提醒重点：{remind_focus}\n子任务安排：\n{subtask_summary}\n\n回复指引：\n1. 回复“进行中 + 备注”可更新任务状态。\n2. 回复“已完成 + 备注”可将任务标记为完成。\n3. 如需延期，请回复“延期 + 新日期 + 原因”。",
    },
    {
        "name": "默认任务更新邮件模板",
        "template_kind": "MAIL_SEND",
        "notify_type": "task_updated",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "您好，{recipient_name}。\n任务已更新，请关注以下变更。\n更新重点：{remind_focus}\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n开始时间：{start_at}\n结束时间：{end_at}\n主任务详情：{task_content}\n主任务备注：{task_remark}\n子任务安排：\n{subtask_summary}\n\n回复指引：\n1. 回复“进行中 + 说明”可更新任务状态。\n2. 回复“已完成 + 说明”可将任务标记为完成。",
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
        "content": "任务提醒：\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n主任务详情：{task_content}\n主任务备注：{task_remark}\n当前提醒重点：{remind_focus}\n子任务安排：\n{subtask_summary}\n请尽快处理并按模板回复邮件反馈状态。",
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
        "content": "任务到期提醒：\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n结束时间：{end_at}\n主任务详情：{task_content}\n主任务备注：{task_remark}\n当前提醒重点：{remind_focus}\n子任务安排：\n{subtask_summary}\n请尽快处理。",
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
        "content": "您好，{recipient_name}。任务创建人：{creator_name}，负责人：{owner_name}。您有新的任务通知，任务编号：{task_id}，任务名称：{task_title}，主任务详情：{task_content}，主任务备注：{task_remark}，当前提醒重点：{remind_focus}，子任务：{subtask_brief}",
    },
    {
        "name": "默认任务更新即时消息模板",
        "template_kind": "QAX_SEND",
        "notify_type": "task_updated",
        "priority": 100,
        "version": 1,
        "enabled": True,
        "is_default": True,
        "subject_rule": "",
        "body_rule": "",
        "content": "任务已更新：{task_title}（任务编号：{task_id}）。更新重点：{remind_focus}。任务创建人：{creator_name}，负责人：{owner_name}，主任务详情：{task_content}，主任务备注：{task_remark}，子任务：{subtask_brief}",
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
        "content": "任务提醒：{task_title}（任务编号：{task_id}），任务创建人：{creator_name}，负责人：{owner_name}，主任务详情：{task_content}，主任务备注：{task_remark}，当前提醒重点：{remind_focus}，子任务：{subtask_brief}，请尽快处理。",
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
        "content": "任务“{task_title}”即将到期（{end_at}），负责人：{owner_name}，主任务详情：{task_content}，主任务备注：{task_remark}，当前提醒重点：{remind_focus}，子任务：{subtask_brief}。",
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
]

LEGACY_DEFAULT_TEMPLATE_CONTENTS = {
    ("MAIL_SEND", "task_created"): "您好，{recipient_name}。\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n开始时间：{start_at}\n结束时间：{end_at}\n子任务安排：\n{subtask_summary}\n\n回复指引：\n1. 回复“进行中 + 备注”可更新任务状态。\n2. 回复“已完成 + 备注”可将任务标记为完成。\n3. 如需延期，请回复“延期 + 新日期 + 原因”。",
    ("MAIL_SEND", "task_updated"): "您好，{recipient_name}。\n任务已更新，请关注以下变更。\n更新重点：{remind_focus}\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n开始时间：{start_at}\n结束时间：{end_at}\n子任务安排：\n{subtask_summary}\n\n回复指引：\n1. 回复“进行中 + 说明”可更新任务状态。\n2. 回复“已完成 + 说明”可将任务标记为完成。",
    ("MAIL_SEND", "manual_remind"): "任务提醒：\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n子任务安排：\n{subtask_summary}\n请尽快处理并按模板回复邮件反馈状态。",
    ("MAIL_SEND", "due_remind"): "任务到期提醒：\n任务创建人：{creator_name}\n负责人：{owner_name}\n任务编号：{task_id}\n任务名称：{task_title}\n结束时间：{end_at}\n子任务安排：\n{subtask_summary}\n请尽快处理。",
    ("QAX_SEND", "task_created"): "您好，{recipient_name}。任务创建人：{creator_name}，负责人：{owner_name}。您有新的任务通知，任务编号：{task_id}，任务名称：{task_title}，子任务：{subtask_brief}",
    ("QAX_SEND", "task_updated"): "任务已更新：{task_title}（任务编号：{task_id}）。更新重点：{remind_focus}。任务创建人：{creator_name}，负责人：{owner_name}，子任务：{subtask_brief}",
    ("QAX_SEND", "manual_remind"): "任务提醒：{task_title}（任务编号：{task_id}），任务创建人：{creator_name}，负责人：{owner_name}，子任务：{subtask_brief}，请尽快处理。",
    ("QAX_SEND", "due_remind"): "任务“{task_title}”即将到期（{end_at}），负责人：{owner_name}，子任务：{subtask_brief}。",
}


def _ensure_schema_columns() -> None:
    """在 SQLite 场景下补齐历史库缺失字段。"""
    with engine.begin() as conn:
        if settings.database_url.startswith("sqlite"):
            task_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()}
            if "due_remind_days" not in task_columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN due_remind_days INTEGER NOT NULL DEFAULT 0"))
            if "completed_at" not in task_columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN completed_at DATETIME"))
            recipient_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(notification_recipients)")).fetchall()}
            if "content_snapshot" not in recipient_columns:
                conn.execute(text("ALTER TABLE notification_recipients ADD COLUMN content_snapshot TEXT NOT NULL DEFAULT ''"))
            if "read_at" not in recipient_columns:
                conn.execute(text("ALTER TABLE notification_recipients ADD COLUMN read_at VARCHAR(64) NOT NULL DEFAULT ''"))
            mail_event_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(mail_events)")).fetchall()}
            if "to_addr" not in mail_event_columns:
                conn.execute(text("ALTER TABLE mail_events ADD COLUMN to_addr TEXT NOT NULL DEFAULT ''"))
            if "original_body" not in mail_event_columns:
                conn.execute(text("ALTER TABLE mail_events ADD COLUMN original_body TEXT NOT NULL DEFAULT ''"))
            if "inbox_protocol" not in mail_event_columns:
                conn.execute(text("ALTER TABLE mail_events ADD COLUMN inbox_protocol VARCHAR(16) NOT NULL DEFAULT ''"))
            if "inbox_folder" not in mail_event_columns:
                conn.execute(text("ALTER TABLE mail_events ADD COLUMN inbox_folder VARCHAR(255) NOT NULL DEFAULT ''"))
            if "server_message_ref" not in mail_event_columns:
                conn.execute(text("ALTER TABLE mail_events ADD COLUMN server_message_ref VARCHAR(255) NOT NULL DEFAULT ''"))
            audit_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(audit_logs)")).fetchall()}
            if "log_level" not in audit_columns:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN log_level VARCHAR(16) NOT NULL DEFAULT 'INFO'"))
            if "module_name" not in audit_columns:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN module_name VARCHAR(64) NOT NULL DEFAULT 'system'"))
            if "message" not in audit_columns:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN message TEXT NOT NULL DEFAULT ''"))
            if "detail_json" not in audit_columns:
                conn.execute(text("ALTER TABLE audit_logs ADD COLUMN detail_json TEXT NOT NULL DEFAULT '{}'"))
            return

        def has_column(table_name: str, column_name: str) -> bool:
            return (
                conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = :table_name AND column_name = :column_name
                        LIMIT 1
                        """
                    ),
                    {"table_name": table_name, "column_name": column_name},
                ).first()
                is not None
            )

        if not has_column("mail_events", "original_body"):
            conn.execute(text("ALTER TABLE mail_events ADD COLUMN original_body TEXT NOT NULL DEFAULT ''"))
        if not has_column("notification_recipients", "read_at"):
            conn.execute(text("ALTER TABLE notification_recipients ADD COLUMN read_at VARCHAR(64) NOT NULL DEFAULT ''"))
        if not has_column("mail_events", "inbox_protocol"):
            conn.execute(text("ALTER TABLE mail_events ADD COLUMN inbox_protocol VARCHAR(16) NOT NULL DEFAULT ''"))
        if not has_column("mail_events", "to_addr"):
            conn.execute(text("ALTER TABLE mail_events ADD COLUMN to_addr TEXT NOT NULL DEFAULT ''"))
        if not has_column("mail_events", "inbox_folder"):
            conn.execute(text("ALTER TABLE mail_events ADD COLUMN inbox_folder VARCHAR(255) NOT NULL DEFAULT ''"))
        if not has_column("mail_events", "server_message_ref"):
            conn.execute(text("ALTER TABLE mail_events ADD COLUMN server_message_ref VARCHAR(255) NOT NULL DEFAULT ''"))


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
                        role="system_admin",
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

        admin_count = db.query(User).filter(User.role.in_(("system_admin", "admin"))).count()
        if admin_count == 0:
            recovered_admin = db.query(User).filter(User.username == "admin").first()
            if recovered_admin:
                recovered_admin.password_hash = hash_password(settings.default_password)
                recovered_admin.role = "system_admin"
                recovered_admin.name = "系统管理员"
                recovered_admin.email = "admin@example.com"
                recovered_admin.ip_address = "10.0.0.1"
                recovered_admin.is_active = True
            else:
                db.add(
                    User(
                        username="admin",
                        password_hash=hash_password(settings.default_password),
                        role="system_admin",
                        name="系统管理员",
                        email="admin@example.com",
                        ip_address="10.0.0.1",
                        is_active=True,
                    )
                )
            db.commit()

        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user and admin_user.role == "admin":
            # 首个内置账号升级为系统管理员，确保新增系统级菜单后仍可维护用户和模板配置。
            admin_user.role = "system_admin"

        existing_keys = {(item.template_kind, item.notify_type, item.name) for item in db.query(Template).all()}
        for template_data in DEFAULT_TEMPLATES:
            key = (template_data["template_kind"], template_data["notify_type"], template_data["name"])
            if key in existing_keys:
                continue
            # 仅补齐缺失模板，避免覆盖管理员在线调整过的模板内容。
            db.add(Template(**template_data))

        deprecated_template_ids = [
            item.id
            for item in db.query(Template.id)
            .filter(
                Template.is_default.is_(True),
                Template.notify_type.in_(("delay_approval", "delay_request", "delay_approve")),
            )
            .all()
        ]
        if deprecated_template_ids:
            deprecated_mail_event_ids = [
                item.id
                for item in db.query(MailEvent.id)
                .filter(MailEvent.resolved_template_id.in_(deprecated_template_ids))
                .all()
            ]
            if deprecated_mail_event_ids:
                db.query(MailAction).filter(MailAction.mail_event_id.in_(deprecated_mail_event_ids)).delete(synchronize_session=False)
                db.query(MailEvent).filter(MailEvent.id.in_(deprecated_mail_event_ids)).delete(synchronize_session=False)
            db.query(Template).filter(Template.id.in_(deprecated_template_ids)).delete(synchronize_session=False)

        latest_default_contents = {
            (item["template_kind"], item["notify_type"]): item["content"]
            for item in DEFAULT_TEMPLATES
            if item["template_kind"] in {"MAIL_SEND", "QAX_SEND"}
        }
        for template in (
            db.query(Template)
            .filter(Template.is_default.is_(True), Template.template_kind.in_(("MAIL_SEND", "QAX_SEND")))
            .all()
        ):
            key = (template.template_kind, template.notify_type)
            legacy_content = LEGACY_DEFAULT_TEMPLATE_CONTENTS.get(key)
            latest_content = latest_default_contents.get(key)
            if legacy_content and latest_content and template.content == legacy_content:
                # 仅在模板仍保持旧版默认正文时自动升级，避免覆盖管理员的自定义编辑。
                template.content = latest_content
            if template.template_kind == "MAIL_SEND" and template.notify_type in {"task_created", "task_updated", "manual_remind", "due_remind"}:
                lines = []
                for line in (template.content or "").splitlines():
                    if "{task_remark}" in line or "延期" in line:
                        continue
                    lines.append(line)
                cleaned = "\n".join(lines).strip()
                if template.notify_type == "task_created" and "进行中" not in cleaned and "已完成" not in cleaned:
                    cleaned = (
                        f"{cleaned}\n\n回复指引：\n"
                        "1. 回复“进行中 + 说明”可更新任务状态。\n"
                        "2. 回复“已完成 + 说明”可将任务标记为完成。"
                    )
                template.content = cleaned
        db.commit()
