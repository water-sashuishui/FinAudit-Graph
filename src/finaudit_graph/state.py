from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class AuditSystemState(TypedDict, total=False):
    """Global state passed between FinAudit-Graph workflow nodes."""

    raw_document_path: str
    parsed_financial_data: dict[str, Any]
    discovered_related_parties: list[dict[str, Any]]
    audit_risks_found: list[dict[str, Any]]
    final_audit_summary: str
    error_message: str

