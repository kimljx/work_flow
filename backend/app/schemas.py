from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ApiMessage(BaseModel):
    message: str


class UserOut(BaseModel):
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
    username: str
    role: str
    name: str
    email: str
    ip_address: str


class UserUpdate(BaseModel):
    role: str
    name: str
    email: str
    ip_address: str
    is_active: bool


class MilestonePayload(BaseModel):
    name: str
    planned_at: datetime
    remind_offsets: list[int] = Field(default_factory=lambda: [1])
    sort_order: int = 0


class TaskCreate(BaseModel):
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


class TaskStatusUpdate(BaseModel):
    main_status: str
    remark: str = ""


class TaskOut(BaseModel):
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
    status_text: str = ""
    priority_text: str = ""
    owner_name: str = ""
    participant_count: int = 0
    notification_total: int = 0
    delivered_count: int = 0
    completed_member_count: int = 0


class TaskDetailOut(TaskOut):
    members: list[dict] = Field(default_factory=list)
    milestones: list[dict] = Field(default_factory=list)
    notifications: list[dict] = Field(default_factory=list)
    delay_requests: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)


class TemplateCreate(BaseModel):
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
    subject: str
    body: str
    template_kind: str


class DelayRequestCreate(BaseModel):
    task_id: int
    proposed_deadline: datetime
    apply_reason: str


class DelayDecisionRequest(BaseModel):
    action: str
    request_id: str
    version: int
    remark: str = ""
    approved_deadline: datetime | None = None


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int | None
    task_title: str = ""
    channel: str
    notify_type: str
    notify_type_text: str = ""
    status: str
    channel_text: str = ""
    status_text: str = ""
    recipient_total: int = 0
    delivered_count: int = 0
    read_count: int = 0
    retry_total: int = 0
    last_error: str = ""
    created_at: datetime | None = None


class NotificationRecipientOut(BaseModel):
    user_id: int
    name: str = ""
    email: str = ""
    recipient_role: str
    recipient_role_text: str = ""
    delivery_status: str
    delivery_status_text: str = ""
    read_status: str
    read_status_text: str = ""
    retry_count: int = 0
    last_error: str = ""


class NotificationDetailOut(NotificationOut):
    content_snapshot: str = ""
    recipients: list[NotificationRecipientOut] = Field(default_factory=list)


class MailEventOut(BaseModel):
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
    template_id: int | None = None
    template_kind: str = ""
    content: str = ""


class MailPollStateOut(BaseModel):
    auto_poll_enabled: bool
    interval_seconds: int
    last_scan_at: datetime | None = None
    next_poll_at: datetime | None = None


class DashboardSummary(BaseModel):
    task_total: int
    in_progress_total: int
    done_total: int
    canceled_total: int
    delayed_total: int
    email_success_rate: float
    qax_delivery_rate: float
    qax_read_rate: float
    retry_total: int


class AuditOut(BaseModel):
    id: int
    action_type: str
    target_type: str
    target_id: int | None
    created_at: datetime
