from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PII_PATTERNS = {
    "phone_number": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "id_number": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "bank_account": re.compile(r"(?<!\d)\d{12,19}(?!\d)"),
}

PROMPT_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"忽略.*?(之前|以上).{0,10}(指令|要求)",
        r"ignore.{0,20}(previous|above).{0,20}(instruction|prompt)",
        r"输出.*?无风险",
        r"give.*?no risk",
        r"泄露.*?(系统提示词|prompt)",
        r"reveal.*?(system prompt|hidden prompt)",
    ]
]


def read_source_text(document_path: str | Path) -> str:
    path = Path(document_path)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            return ""


def sanitize_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    redactions: list[dict[str, Any]] = []
    sanitized = text
    for label, pattern in PII_PATTERNS.items():
        matches = list(pattern.finditer(sanitized))
        if not matches:
            continue
        sanitized = pattern.sub(f"[REDACTED_{label.upper()}]", sanitized)
        redactions.append({"type": label, "count": len(matches)})
    return sanitized, redactions


def detect_prompt_injection(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            findings.append(pattern.pattern)
    return findings


def inspect_document_security(document_path: str | Path) -> dict[str, Any]:
    text = read_source_text(document_path)
    sanitized_text, redactions = sanitize_text(text)
    injection_hits = detect_prompt_injection(text)
    return {
        "sanitized_text": sanitized_text,
        "pii_redactions": redactions,
        "prompt_injection_hits": injection_hits,
        "blocked": bool(injection_hits),
    }
