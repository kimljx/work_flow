from __future__ import annotations

TASK_STATUS_LABELS = {
    "not_started": "未开始",
    "in_progress": "进行中",
    "done": "已完成",
    "canceled": "已取消",
}

TASK_STATUS_OPTIONS = list(TASK_STATUS_LABELS.keys())

ROLE_LABELS = {
    "admin": "管理员",
    "member": "成员",
}

MEMBER_ROLE_LABELS = {
    "owner": "负责人",
    "participant": "参与者",
    "admin": "管理员",
}

NOTIFICATION_CHANNEL_LABELS = {
    "email": "邮件",
    "qax": "QAX 通知",
}

NOTIFICATION_TYPE_LABELS = {
    "task_created": "任务创建通知",
    "manual_remind": "手动提醒",
    "due_remind": "到期提醒",
    "delay_approval": "延期审批通知",
    "task_done": "邮件回执-已完成",
    "task_in_progress": "邮件回执-进行中",
    "delay_request": "邮件回执-延期申请",
    "delay_approve": "邮件回执-延期审批",
}

TEMPLATE_NOTIFY_TYPE_OPTIONS = {
    "MAIL_SEND": ["task_created", "manual_remind", "due_remind", "delay_approval"],
    "QAX_SEND": ["task_created", "manual_remind", "due_remind", "delay_approval"],
    "MAIL_REPLY": ["task_done", "task_in_progress", "delay_request", "delay_approve"],
}

NOTIFICATION_STATUS_LABELS = {
    "pending": "待处理",
    "sent": "已发送",
    "delivered": "已送达",
    "failed": "发送失败",
}

READ_STATUS_LABELS = {
    "unread": "未读",
    "read": "已读",
}

DELAY_STATUS_LABELS = {
    "PENDING": "待审批",
    "APPROVED": "已通过",
    "REJECTED": "已拒绝",
}

PRIORITY_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

MAIL_EVENT_STATUS_LABELS = {
    "NEW": "新邮件",
    "UNMATCHED": "未匹配模板",
    "MATCHED": "已匹配模板",
    "APPLIED": "已应用业务动作",
    "SKIPPED": "已跳过",
    "FAILED": "处理失败",
}

MAIL_ACTION_STATUS_LABELS = {
    "NEW": "待处理",
    "APPLIED": "已执行",
    "SKIPPED": "已跳过",
    "FAILED": "执行失败",
}
