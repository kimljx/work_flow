from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

MAX_SCAN_LINES = 20
APPROVE_RE = re.compile(r"^\s*(同意|批准)\s*[:：+\s]\s*(?P<date>\d{4}-\d{1,2}-\d{1,2}|\d{4}年\d{1,2}月\d{1,2}日)\s*(?P<remark>.*)$")
REJECT_RE = re.compile(r"^\s*(拒绝|驳回)\s*[:：+\s]?\s*(?P<remark>.*)$")


@dataclass
class DelayParseResult:
    ok: bool
    action: str = ""
    date: datetime | None = None
    remark: str = ""
    error_code: str = ""


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("：", ":").replace("　", " ")


def parse_date(text: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_delay_approval_email(text: str) -> DelayParseResult:
    lines = [line.strip() for line in normalize_text(text).split("\n") if line.strip()][:MAX_SCAN_LINES]
    for line in lines:
        if line.startswith(">"):
            continue
        approve_match = APPROVE_RE.match(line)
        if approve_match:
            parsed_date = parse_date(approve_match.group("date"))
            if not parsed_date:
                return DelayParseResult(ok=False, error_code="INVALID_DATE")
            return DelayParseResult(ok=True, action="APPROVE", date=parsed_date, remark=approve_match.group("remark").strip())
        reject_match = REJECT_RE.match(line)
        if reject_match:
            return DelayParseResult(ok=True, action="REJECT", remark=reject_match.group("remark").strip())
    return DelayParseResult(ok=False, error_code="PARSE_FAILED")
