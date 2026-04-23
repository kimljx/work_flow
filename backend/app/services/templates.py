from __future__ import annotations

"""模板匹配服务。"""

from app.models import Template


RULE_SEPARATORS = ("|", "\n", "，", ",", "；", ";")


def _split_rule(rule: str) -> list[str]:
    """将模板规则按多种分隔符拆分为关键词列表。"""
    normalized = rule or ""
    for separator in RULE_SEPARATORS:
        normalized = normalized.replace(separator, "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def template_matches(template: Template, subject: str, body: str) -> bool:
    """判断邮件主题或正文是否命中某个模板。"""
    subject_text = (subject or "").lower()
    body_text = (body or "").lower()
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
