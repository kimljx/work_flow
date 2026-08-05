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
QUOTE_SEPARATOR_PATTERN = re.compile(
    r"^-{3,}\s*(?:original message|forwarded message|\u539f\u90ae\u4ef6\u4fe1\u606f|\u539f\u59cb\u90ae\u4ef6|\u8f6c\u53d1\u90ae\u4ef6)\s*-{3,}$",
    re.IGNORECASE,
)
QUOTE_METADATA_PATTERN = re.compile(
    r"^(?:from|sender|to|subject|date|\u53d1\u4ef6\u4eba|\u5bc4\u4ef6\u8005|\u53d1\u9001\u65f6\u95f4|\u6536\u4ef6\u4eba|\u4e3b\u9898)\s*[:\uff1a]",
    re.IGNORECASE,
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
    "task_remark",
    "remind_focus",
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


def _is_dashed_original_mail_separator(raw_lines: list[str], index: int) -> bool:
    if not re.fullmatch(r"-{3,}", raw_lines[index].strip()):
        return False
    return any(QUOTE_METADATA_PATTERN.match(item.strip()) for item in raw_lines[index + 1:index + 7])


def strip_reply_guides(body: str) -> str:
    """剔除正文中的回复指引与引用原文。

    该能力既用于邮件回执匹配，也用于将邮件模板改造成 QAX 正文时移除“请按邮件回复”的提示，
    避免即时消息正文里混入无法执行的交互说明。
    """
    normalized_lines: list[str] = []
    skip_guide_block = False
    raw_lines = (body or "").splitlines()
    for index, raw_line in enumerate(raw_lines):
        line = raw_line.strip()
        lower_line = line.lower()
        if (
            _is_dashed_original_mail_separator(raw_lines, index)
            or QUOTE_SEPARATOR_PATTERN.match(line)
            or QUOTE_METADATA_PATTERN.match(line)
            or any(lower_line.startswith(pattern) for pattern in QUOTE_START_PATTERNS)
        ):
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
    body_text = strip_reply_guides(body).lower()
    subject_rules = _split_rule(template.subject_rule)
    body_rules = _split_rule(template.body_rule)

    if subject_rules and any(rule.lower() in subject_text for rule in subject_rules):
        return True
    if body_rules and any(rule.lower() in body_text for rule in body_rules):
        return True
    return False


def select_reply_template(templates: list[Template], subject: str, body: str) -> Template | None:
    """按回复中最先出现的状态词选择模板。

    同一封回信可能在进度说明中同时出现“进行中”和“已完成”。此时优先级不应
    覆盖用户最先填写的状态：先检查主题，主题未包含状态词时再检查正文；在同一
    段文本中，位置更靠前的规则胜出。换行后的状态词自然位于更后的位置，因此不
    会改变首个状态的判断。相同位置才以模板优先级、版本和 ID 决定结果。
    """
    for text, rule_attr in ((subject or "", "subject_rule"), (strip_reply_guides(body), "body_rule")):
        text = text.lower()
        matches: list[tuple[int, int, int, int, Template]] = []
        for template in templates:
            positions = [text.find(rule.lower()) for rule in _split_rule(getattr(template, rule_attr))]
            positions = [position for position in positions if position >= 0]
            if positions:
                matches.append((min(positions), -template.priority, -template.version, template.id, template))
        if matches:
            return min(matches, key=lambda item: item[:4])[4]
    return None


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
