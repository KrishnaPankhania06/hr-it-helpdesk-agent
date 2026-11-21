"""Guardrails: prompt-injection blocking, PII redaction, HR/IT scope control."""
import re

# ---------------------------------------------------------------- injection
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+)?(previous|prior|your)\s+(instructions?|programming|rules?)",
    r"forget\s+(your|all|everything|previous)",
    r"(print|show|reveal|repeat|tell me|leak)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions?|system\s+message)",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(a\s+)?(different|new|another|an?\s+unrestricted)",
    r"\bDAN\b",
    r"jailbreak",
    r"no\s+(restrictions?|filters?|limits?|rules?)\s+(mode|anymore|now)?",
    r"new\s+persona",
    r"override\s+(your|the|all)\s+(instructions?|rules?|guardrails?|safety)",
    r"pretend\s+(to\s+be|you\s+are|that\s+you)",
    r"bypass\s+(your|the|all)\s+(guardrails?|filters?|safety|restrictions?)",
]


def detect_prompt_injection(text):
    """Return (is_injection, matched_pattern_or_None)."""
    lowered = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lowered, re.IGNORECASE):
            return True, pattern
    return False, None


# -------------------------------------------------------------------- PII
PII_PATTERNS = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("aadhaar", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")),
    ("pan", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{4}\s?\d{5}(?!\d)")),
    ("credit_card", re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b")),
]


def redact_pii(text):
    """Mask PII in a string. Returns (redacted_text, list_of_kinds_redacted)."""
    redacted_kinds = []
    out = text
    for kind, pattern in PII_PATTERNS:
        if pattern.search(out):
            redacted_kinds.append(kind)
            out = pattern.sub(f"[REDACTED {kind.upper()}]", out)
    return out, redacted_kinds


# -------------------------------------------------------------------- scope
HR_IT_KEYWORDS = [
    "leave", "vacation", "holiday", "sick", "wfh", "work from home", "remote work",
    "policy", "policies", "benefit", "insurance", "pf", "provident", "gratuity",
    "reimbursement", "allowance", "onboarding", "probation", "notice period",
    "payroll", "salary slip", "laptop", "asset", "password", "vpn", "wifi",
    "printer", "phishing", "security", "mfa", "email access", "laptop", "mouse",
    "keyboard", "monitor", "headset", "it helpdesk", "hr ", "human resources",
    "counselling", "counseling", "learning budget", "internet allowance",
    "carry over", "carryover", "accrue", "manager", "department", "employee",
    "sabbatical", "maternity", "paternity", "attendance", "timesheet",
    "suspicious", "spam", "email", "account locked", "access card", "id card",
]

EMPLOYEE_ID_RE = re.compile(r"\bE\d{3}\b", re.IGNORECASE)


def find_employee_id(text):
    m = EMPLOYEE_ID_RE.search(text)
    return m.group(0).upper() if m else None


def is_hr_it_topic(text):
    lowered = text.lower()
    return any(k in lowered for k in HR_IT_KEYWORDS) or bool(EMPLOYEE_ID_RE.search(text))
