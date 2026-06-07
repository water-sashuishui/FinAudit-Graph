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
    negotiation_trace: list[dict[str, Any]]
    llm_provider: str
    error_message: str
    neo4j_configured: bool
    neo4j_available: bool
    graph_write_status: str
    graph_write_error: str
    graph_records_written: int
    graph_source: str
