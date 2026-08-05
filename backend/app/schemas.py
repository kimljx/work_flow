from __future__ import annotations

"""Pydantic 接口模型定义。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenPair(BaseModel):
    """登录与刷新接口返回的令牌对。"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """登录请求体。"""
    username: str
    password: str
    password_legacy_sha256: str = ""


class RefreshRequest(BaseModel):
    """刷新令牌请求体。"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """当前用户修改密码请求体，密码字段由前端 MD5 后提交。"""
    current_password: str
    new_password: str
    current_password_legacy_sha256: str = ""


class ResetPasswordRequest(BaseModel):
    """管理员重置指定用户密码请求体，密码字段由前端 MD5 后提交。"""
    new_password: str


class ApiMessage(BaseModel):
    """统一的简单提示消息响应。"""
    message: str


class NotificationBulkDeleteRequest(BaseModel):
    """批量删除通知请求。"""
    ids: list[int] = Field(default_factory=list)


class MailEventBulkDeleteRequest(BaseModel):
    """批量删除收件落库记录请求。"""
    ids: list[int] = Field(default_factory=list)


class UserOut(BaseModel):
    """用户输出模型。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    name: str
    email: str
    ip_address: str
    is_active: bool
    role_text: str = ""


class UserCreate(BaseModel):
    """创建用户请求体。"""
    username: str
    role: str
    name: str
    email: str
    ip_address: str


class UserUpdate(BaseModel):
    """更新用户请求体。"""
    role: str
    name: str
    email: str
    ip_address: str
    is_active: bool


class MilestonePayload(BaseModel):
    """任务里程碑输入结构。"""
    name: str
    planned_at: datetime
    remind_offsets: list[int] = Field(default_factory=lambda: [1])
    sort_order: int = 0


class SubtaskPayload(BaseModel):
    """任务子任务输入结构。"""
    id: int | None = None
    title: str
    content: str = ""
    assignee_id: int
    sort_order: int = 0
    status: str = "pending"


class TaskCreate(BaseModel):
    """任务创建与编辑通用请求体。"""
    title: str
    content: str
    owner_id: int
    participant_ids: list[int]
    start_at: datetime
    end_at: datetime
    due_remind_days: int = 0
    priority: str
    remark: str = ""
    milestones: list[MilestonePayload] = Field(default_factory=list)
    subtasks: list[SubtaskPayload] = Field(default_factory=list)


class TaskStatusUpdate(BaseModel):
    """任务状态更新请求体。"""
    main_status: str
    remark: str = ""


class TaskOut(BaseModel):
    """任务列表输出结构。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    content: str
    remark: str = ""
    priority: str
    main_status: str
    delay_days: int
    state_locked: bool
    due_remind_days: int
    start_at: datetime
    end_at: datetime
    planned_minutes: int
    actual_minutes: int
    completed_at: datetime | None = None
    status_text: str = ""
    priority_text: str = ""
    owner_name: str = ""
    creator_name: str = ""
    responsible_names: list[str] = Field(default_factory=list)
    participant_count: int = 0
    notification_total: int = 0
    delivered_count: int = 0
    completed_member_count: int = 0
    subtask_count: int = 0
    subtask_status_summary: list[dict] = Field(default_factory=list)
    latest_notifications: dict[str, dict] = Field(default_factory=dict)
    notification_sending: bool = False
    created_at: datetime | None = None


class TaskDetailOut(TaskOut):
    """任务详情输出结构，补充成员、通知、延期与状态流水。"""
    members: list[dict] = Field(default_factory=list)
    milestones: list[dict] = Field(default_factory=list)
    subtasks: list[dict] = Field(default_factory=list)
    notifications: list[dict] = Field(default_factory=list)
    delay_requests: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    """模板新增与编辑请求体。"""
    name: str
    template_kind: str
    notify_type: str
    priority: int = 100
    version: int = 1
    enabled: bool = True
    is_default: bool = False
    subject_rule: str = ""
    body_rule: str = ""
    content: str = ""


class TemplatePreviewRequest(BaseModel):
    """模板预匹配调试请求体。"""
    subject: str
    body: str
    template_kind: str


class DelayRequestCreate(BaseModel):
    """延期申请创建请求体。"""
    task_id: int
    proposed_deadline: datetime
    apply_reason: str


class DelayDecisionRequest(BaseModel):
    """延期审批请求体。"""
    action: str
    request_id: str
    version: int
    remark: str = ""
    approved_deadline: datetime | None = None


class NotificationOut(BaseModel):
    """通知列表输出结构。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int | None
    task_title: str = ""
    channel: str
    notify_type: str
    notify_type_text: str = ""
    notify_scene_text: str = ""
    feedback_label: str = ""
    status: str
    channel_text: str = ""
    status_text: str = ""
    recipient_total: int = 0
    delivered_count: int = 0
    read_count: int = 0
    retry_total: int = 0
    last_error: str = ""
    remind_focus: str = ""
    created_at: datetime | None = None


class NotificationRecipientOut(BaseModel):
    """通知详情中的成员送达与回复状态结构。"""
    user_id: int
    name: str = ""
    email: str = ""
    recipient_role: str
    recipient_role_text: str = ""
    delivery_status: str
    delivery_status_text: str = ""
    read_status: str
    read_status_text: str = ""
    read_at: str = ""
    feedback_label: str = ""
    retry_count: int = 0
    content_snapshot: str = ""
    last_error: str = ""


class NotificationDetailOut(NotificationOut):
    """通知详情输出结构，包含正文快照与接收人明细。"""
    content_snapshot: str = ""
    recipients: list[NotificationRecipientOut] = Field(default_factory=list)


class NotificationPreviewOut(BaseModel):
    channel: str
    channel_text: str = ""
    notify_type: str
    notify_type_text: str = ""
    recipient_user_id: int | None = None
    recipient_name: str = ""
    recipient_email: str = ""
    template_name: str = ""
    template_version: int | None = None
    subject: str = ""
    content: str = ""
    context: dict[str, str] = Field(default_factory=dict)


class TaskImportHistoryOut(BaseModel):
    """任务导入历史输出结构。"""
    id: int
    filename: str = ""
    operator_name: str = ""
    total_rows: int = 0
    success_count: int = 0
    failure_count: int = 0
    overlap_count: int = 0
    confirmed_duplicate: bool = False
    overlap_samples: list[dict] = Field(default_factory=list)
    failure_samples: list[dict] = Field(default_factory=list)
    created_at: datetime | None = None


class TaskImportPreviewOut(BaseModel):
    """任务导入预检结果结构。"""
    message: str
    needs_confirmation: bool = False
    overlap_count: int = 0
    overlap_rate: float = 0
    overlap_samples: list[dict] = Field(default_factory=list)


class MailEventOut(BaseModel):
    """邮件列表输出结构。"""
    id: int
    message_id: str
    from_addr: str
    subject: str
    body_digest: str
    process_status: str
    process_status_text: str = ""
    template_name: str = ""
    notify_type: str = ""
    notify_type_text: str = ""
    task_id: int | None = None
    task_title: str = ""
    action_type: str = ""
    action_status: str = ""
    action_status_text: str = ""
    action_result_json: str = ""
    created_at: datetime | None = None


class MailEventDetailOut(MailEventOut):
    """邮件详情输出结构。"""
    template_id: int | None = None
    template_kind: str = ""
    content: str = ""
    original_body: str = ""


class MailPollStateOut(BaseModel):
    """邮件轮询状态输出结构。"""
    inbox_protocol: str = "imap"
    inbox_protocol_text: str = "IMAP"
    auto_poll_enabled: bool
    interval_seconds: int
    last_scan_at: datetime | None = None
    next_poll_at: datetime | None = None
    baseline_started_at: datetime | None = None
    qax_auto_collect_enabled: bool = False
    qax_interval_seconds: int = 3600
    qax_browser_visible: bool = False


class HostIpMappingPayload(BaseModel):
    id: int | None = None
    host: str
    ip: str = ""
    enabled: bool = True
    source: str = "manual"
    note: str = ""


class RuntimeSettingsUpdate(BaseModel):
    mail_auto_poll_enabled: bool
    mail_auto_poll_interval_seconds: int = 300
    mail_inbox_max_scan: int = 20
    due_remind_enabled: bool = True
    due_remind_run_at: str = "09:00"
    overdue_remind_enabled: bool = True
    overdue_remind_run_at: str = "09:00"
    completed_mail_cleanup_enabled: bool = True
    completed_mail_cleanup_retention_days: int = 30
    system_log_cleanup_enabled: bool = True
    system_log_retention_days: int = 60
    system_log_cleanup_interval_seconds: int = 86400
    qax_auto_collect_enabled: bool
    qax_auto_collect_interval_seconds: int = 3600
    mail_scan_baseline_at: datetime | None = None
    qax_browser_visible: bool = False
    qax_base_url: str = ""
    qax_username: str = ""
    qax_password: str = ""
    qax_group_name: str = ""
    qax_ignore_https_errors: bool = True
    smtp_host: str = ""
    smtp_port: int = 25
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = False
    smtp_timeout_seconds: int = 20
    mail_inbox_protocol: str = "imap"
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_use_tls: bool = False
    imap_use_ssl: bool = True
    pop3_host: str = ""
    pop3_port: int = 110
    pop3_user: str = ""
    pop3_password: str = ""
    pop3_use_tls: bool = False
    pop3_use_ssl: bool = False
    mail_inbox_folders: str = ""
    dns_auto_resolve_enabled: bool = True
    mail_host_mappings: list[HostIpMappingPayload] = []


class MailBaselineRequest(BaseModel):
    baseline_at: datetime | None = None


class DashboardKpi(BaseModel):
    label: str
    value: float | int
    unit: str = ""
    detail: str = ""
    tone: str = "neutral"


class DashboardDistributionItem(BaseModel):
    key: str
    label: str
    value: int


class DashboardTrendPoint(BaseModel):
    label: str
    created_total: int = 0
    completed_total: int = 0
    delayed_total: int = 0


class DashboardAttentionItem(BaseModel):
    title: str
    description: str
    value: str = ""
    tone: str = "neutral"
    route: str = ""
    action_label: str = ""


class DashboardOwnerTaskItem(BaseModel):
    owner_name: str
    task_total: int = 0
    done_total: int = 0
    delayed_total: int = 0
    due_soon_total: int = 0


class DashboardWarningTask(BaseModel):
    task_id: int
    title: str
    owner_name: str = ""
    end_at: datetime
    delay_days: int = 0
    warning_type: str
    warning_text: str
    route: str = ""


class DashboardQuickAction(BaseModel):
    title: str
    description: str
    route: str
    action_label: str
    tone: str = "neutral"


class DashboardSummary(BaseModel):
    """管理员看板汇总指标。"""
    task_total: int
    in_progress_total: int
    done_total: int
    canceled_total: int
    delayed_total: int
    pending_total: int = 0
    due_soon_total: int = 0
    completion_rate: float = 0
    healthy_task_rate: float = 0
    email_success_rate: float
    qax_delivery_rate: float
    qax_read_rate: float
    retry_total: int
    pending_delay_requests: int = 0
    mail_failure_total: int = 0
    health_score: int = 0
    kpis: list[DashboardKpi] = Field(default_factory=list)
    status_distribution: list[DashboardDistributionItem] = Field(default_factory=list)
    priority_distribution: list[DashboardDistributionItem] = Field(default_factory=list)
    task_trend: list[DashboardTrendPoint] = Field(default_factory=list)
    attention_items: list[DashboardAttentionItem] = Field(default_factory=list)
    owner_task_distribution: list[DashboardOwnerTaskItem] = Field(default_factory=list)
    warning_tasks: list[DashboardWarningTask] = Field(default_factory=list)
    quick_actions: list[DashboardQuickAction] = Field(default_factory=list)


class AuditOut(BaseModel):
    """系统日志输出结构。"""
    id: int
    log_level: str = ""
    module_name: str = ""
    action_type: str
    message: str = ""
    operator_id: int | None = None
    operator_name: str = ""
    target_type: str
    target_id: int | None
    source_ip: str = ""
    before_json: str = "{}"
    after_json: str = "{}"
    detail_json: str = "{}"
    created_at: datetime
