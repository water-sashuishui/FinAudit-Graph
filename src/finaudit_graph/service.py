from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from .automation import build_n8n_payload, send_to_n8n
from .knowledge import AUDIT_STANDARD_PATH, retrieve_audit_standards
from .reporting import build_full_report_markdown, save_reports
from .security import inspect_document_security
from .settings import ProjectSettings
from .vector_store import DEFAULT_VECTOR_STORE_PATH, LocalVectorStore
from .workflow import run_demo

SUPPORTED_DOCUMENT_SUFFIXES = {".txt", ".pdf", ".docx", ".xlsx", ".xls", ".csv"}


def execute_audit(
    document_path: str | Path,
    *,
    save_report: bool = False,
    output_dir: str | Path = "outputs",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Run the end-to-end audit workflow and normalize the result shape."""
    normalized_path = validate_document_path(document_path)
    security_result = inspect_document_security(normalized_path)

    if security_result["blocked"]:
        return {
            "request_id": request_id or uuid4().hex,
            "status": "blocked_for_review",
            "document_path": str(normalized_path),
            "parsed_financial_data": {},
            "related_parties": [],
            "audit_risks": [],
            "negotiation_trace": [],
            "llm_provider": "",
            "final_report_markdown": "",
            "n8n_result": {"sent": False, "mode": "blocked"},
            "warnings": [
                "Prompt injection risk detected. Automatic audit was blocked for manual review.",
            ],
            "security_flags": security_result,
        }

    workflow_state = run_demo(str(normalized_path))
    warnings = collect_warnings(workflow_state, security_result)
    report = build_full_report_markdown(workflow_state)
    n8n_result = send_to_n8n(build_n8n_payload(workflow_state))

    result: dict[str, Any] = {
        "request_id": request_id or uuid4().hex,
        "status": "completed",
        "document_path": str(normalized_path),
        "parsed_financial_data": workflow_state.get("parsed_financial_data", {}),
        "related_parties": workflow_state.get("discovered_related_parties", []),
        "audit_risks": workflow_state.get("audit_risks_found", []),
        "negotiation_trace": workflow_state.get("negotiation_trace", []),
        "llm_provider": workflow_state.get("llm_provider", ""),
        "final_report_markdown": report,
        "n8n_result": n8n_result,
        "warnings": warnings,
        "security_flags": security_result,
    }
    if save_report:
        result["report_paths"] = save_reports(workflow_state, output_dir=output_dir)
    return result


def validate_document_path(document_path: str | Path) -> Path:
    path = Path(document_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    if path.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise ValueError(f"Unsupported file type: {path.suffix or '<none>'}")
    return path


def save_uploaded_document(
    filename: str,
    content: bytes,
    *,
    raw_dir: str | Path = "data/raw",
) -> Path:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise ValueError(f"Unsupported file type: {suffix or '<none>'}")

    target_dir = Path(raw_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid4().hex}_{Path(filename).name}"
    target_path.write_bytes(content)
    return target_path


def query_audit_standards(query: str, limit: int = 5) -> dict[str, Any]:
    return {
        "query": query,
        "limit": limit,
        "results": retrieve_audit_standards([query], limit=limit),
    }


def rebuild_rag_index() -> dict[str, Any]:
    records = LocalVectorStore(DEFAULT_VECTOR_STORE_PATH).build_from_json(AUDIT_STANDARD_PATH)
    return {
        "vector_store": str(DEFAULT_VECTOR_STORE_PATH),
        "vector_db": "chroma",
        "embedding_model": "local_hashing_v1",
        "records": len(records),
    }


def build_config_status(settings: ProjectSettings | None = None) -> dict[str, Any]:
    current = settings or ProjectSettings.from_env()
    return {
        "deepseek_configured": bool(current.deepseek_api_key and current.audit_llm_model),
        "neo4j_configured": bool(current.neo4j_uri and current.neo4j_password != "password"),
        "n8n_configured": bool(current.n8n_webhook_url),
        "feishu_configured": bool(
            current.feishu_app_id
            and current.feishu_app_secret
            and current.feishu_base_app_token
            and current.feishu_table_id
        ),
        "audit_llm_model": current.audit_llm_model,
        "deepseek_base_url": current.deepseek_base_url,
    }


def collect_warnings(workflow_state: dict[str, Any], security_result: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    parsed = workflow_state.get("parsed_financial_data", {})
    if workflow_state.get("error_message"):
        warnings.append(str(workflow_state["error_message"]))
    if not parsed:
        warnings.append("No structured financial fields were extracted from the source document.")
    if not workflow_state.get("discovered_related_parties"):
        warnings.append("No related-party clues were found in the current graph source.")
    if not workflow_state.get("audit_risks_found"):
        warnings.append("No audit risks were identified by the current workflow.")
    if security_result.get("pii_redactions"):
        warnings.append("Sensitive fields were detected and masked before model-facing processing.")
    return warnings
