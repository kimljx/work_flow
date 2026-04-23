from __future__ import annotations

"""模板匹配服务。"""

import re

from fastapi import HTTPException

from app.models import Template


RULE_SEPARATORS = ("|", "\n", "，", ",", "；", ";")
PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]+)\}")
REPLY_GUIDE_MARKERS = (
    "回复指引",
    "请按“任务ID",
    "请按\"任务ID",
    "可直接回复",
    "同意 + 新日期",
    "拒绝 + 原因",
)
QUOTE_START_PATTERNS = (
    "-----original message-----",
    "发件人:",
    "from:",
)
COMMON_TEMPLATE_VARIABLES = {
    "task_id",
    "task_title",
    "task_content",
    "start_at",
    "end_at",
    "owner_name",
    "creator_name",
    "recipient_name",
    "subtask_summary",
    "subtask_brief",
    "reply_guide",
}
DELAY_APPROVAL_VARIABLES = {
    "delay_request_id",
    "applicant_name",
    "proposed_deadline",
    "apply_reason",
}


def _split_rule(rule: str) -> list[str]:
    """将模板规则按多种分隔符拆分为关键词列表。"""
    normalized = rule or ""
    for separator in RULE_SEPARATORS:
        normalized = normalized.replace(separator, "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def _strip_reply_guides(body: str) -> str:
    """剔除系统下发邮件中的回复指引与引用原文，避免误触发回复模板。"""
    normalized_lines: list[str] = []
    skip_guide_block = False
    for raw_line in (body or "").splitlines():
        line = raw_line.strip()
        lower_line = line.lower()
        if any(lower_line.startswith(pattern) for pattern in QUOTE_START_PATTERNS):
            break
        if any(marker.lower() in lower_line for marker in REPLY_GUIDE_MARKERS):
            skip_guide_block = True
            continue
        if skip_guide_block:
            if re.match(r"^\d+[\.、\)]", line) or not line:
                continue
            skip_guide_block = False
        if line.startswith(">"):
            continue
        normalized_lines.append(line)
    return "\n".join(item for item in normalized_lines if item).strip()


def template_matches(template: Template, subject: str, body: str) -> bool:
    """判断邮件主题或正文是否命中某个模板。"""
    subject_text = (subject or "").lower()
    body_text = _strip_reply_guides(body).lower()
    subject_rules = _split_rule(template.subject_rule)
    body_rules = _split_rule(template.body_rule)

    if subject_rules and any(rule.lower() in subject_text for rule in subject_rules):
        return True
    if body_rules and any(rule.lower() in body_text for rule in body_rules):
        return True
    return False


def sort_templates(templates: list[Template]) -> list[Template]:
    """按优先级、版本号和主键顺序排序模板。"""
    return sorted(templates, key=lambda item: (-item.priority, -item.version, item.id))


def template_allowed_variables(template_kind: str, notify_type: str) -> set[str]:
    """返回指定模板类型可使用的占位符集合。

    只有发送类模板会参与正文渲染，因此回复匹配模板不允许声明正文占位符，
    避免配置上出现“看起来能用、实际完全不会渲染”的误导。
    """
    if template_kind not in {"MAIL_SEND", "QAX_SEND"}:
        return set()
    variables = set(COMMON_TEMPLATE_VARIABLES)
    if notify_type == "delay_approval":
        variables.update(DELAY_APPROVAL_VARIABLES)
    return variables


def extract_template_placeholders(content: str) -> list[str]:
    """提取模板正文中的占位符名称列表。"""
    return sorted(set(PLACEHOLDER_PATTERN.findall(content or "")))


def validate_template_content(template_kind: str, notify_type: str, content: str) -> None:
    """校验模板正文占位符是否与模板类型匹配。

    当模板里写入不存在的变量时，最终邮件会残留原始占位符文本，因此在保存阶段直接拦截，
    比等到通知发送后再排查更安全。
    """
    placeholders = extract_template_placeholders(content)
    if not placeholders:
        return
    allowed_variables = template_allowed_variables(template_kind, notify_type)
    invalid_variables = [item for item in placeholders if item not in allowed_variables]
    if invalid_variables:
        raise HTTPException(
            status_code=400,
            detail=f"模板中存在无效占位符：{', '.join(invalid_variables)}",
        )
