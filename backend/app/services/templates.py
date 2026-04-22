from __future__ import annotations

from app.models import Template


RULE_SEPARATORS = ("|", "\n", "，", ",", "；", ";")


def _split_rule(rule: str) -> list[str]:
    normalized = rule or ""
    for separator in RULE_SEPARATORS:
        normalized = normalized.replace(separator, "|")
    return [item.strip() for item in normalized.split("|") if item.strip()]


def template_matches(template: Template, subject: str, body: str) -> bool:
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
    return sorted(templates, key=lambda item: (-item.priority, -item.version, item.id))
