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
    """执行端到端审计，并把工作流状态整理成 API/前端统一消费的结果结构。

    这里是服务层的主入口：先校验文件和安全风险，再运行工作流，最后补齐
    报告、自动化结果、告警和安全标记。安全拦截会直接返回人工复核状态。
    """
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
    """校验输入文件是否存在且属于当前系统支持的审计材料格式。"""
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
    """保存上传文件到原始材料目录，并用 UUID 前缀避免同名文件覆盖。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_SUFFIXES:
        raise ValueError(f"Unsupported file type: {suffix or '<none>'}")

    target_dir = Path(raw_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid4().hex}_{Path(filename).name}"
    target_path.write_bytes(content)
    return target_path


def query_audit_standards(query: str, limit: int = 5) -> dict[str, Any]:
    """封装审计准则检索结果，供 FastAPI 和其他调用方直接返回。"""
    return {
        "query": query,
        "limit": limit,
        "results": retrieve_audit_standards([query], limit=limit),
    }


def rebuild_rag_index() -> dict[str, Any]:
    """从本地审计准则 JSON 重建向量索引，并返回索引元信息。"""
    records = LocalVectorStore(DEFAULT_VECTOR_STORE_PATH).build_from_json(AUDIT_STANDARD_PATH)
    return {
        "vector_store": str(DEFAULT_VECTOR_STORE_PATH),
        "vector_db": "chroma",
        "embedding_model": "local_hashing_v1",
        "records": len(records),
    }


def build_config_status(settings: ProjectSettings | None = None) -> dict[str, Any]:
    """汇总外部依赖配置状态，用于健康检查和演示页展示。"""
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
    """根据工作流输出和安全检查结果生成可读告警列表。"""
    warnings: list[str] = []
    parsed = workflow_state.get("parsed_financial_data", {})
    if workflow_state.get("error_message"):
        warnings.append(str(workflow_state["error_message"]))
    if parsed and not parsed.get("extraction_complete", True):
        warnings.append("Financial document extraction is incomplete; review extraction_warnings before relying on risks.")
    if not parsed:
        warnings.append("No structured financial fields were extracted from the source document.")
    if not workflow_state.get("discovered_related_parties"):
        warnings.append("No related-party clues were found in the current graph source.")
    if not workflow_state.get("audit_risks_found"):
        warnings.append("No audit risks were identified by the current workflow.")
    if security_result.get("pii_redactions"):
        warnings.append("Sensitive fields were detected and masked before model-facing processing.")
    return warnings
