from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class AuditSystemState(TypedDict, total=False):
    """FinAudit-Graph 节点之间传递的共享状态。

    ``total=False`` 表示每个节点只需要写入自己负责的字段；这样解析、图谱、
    风险识别和报告生成可以按阶段逐步补全状态。
    """

    # 输入与材料解析结果。
    raw_document_path: str
    parsed_financial_data: dict[str, Any]

    # 图谱检索和风险识别结果。
    discovered_related_parties: list[dict[str, Any]]
    audit_risks_found: list[dict[str, Any]]

    # 报告与多智能体协商信息。
    final_audit_summary: str
    negotiation_trace: list[dict[str, Any]]
    llm_provider: str

    # 运行期错误与外部图谱依赖状态。
    error_message: str
    neo4j_configured: bool
    neo4j_available: bool
    graph_write_status: str
    graph_write_error: str
    graph_records_written: int
    graph_source: str
