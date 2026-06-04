from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict

# 这是整个工作流共享的状态容器。
# 每个节点都从这里读取上游结果，并把自己的产物写回同一个 state。

class AuditSystemState(TypedDict, total=False):
    """Global state passed between FinAudit-Graph workflow nodes."""

    # 原始输入
    raw_document_path: str
    # 解析后的财务结构化字段
    parsed_financial_data: dict[str, Any]
    # 图谱或 fallback 找到的关联方线索
    discovered_related_parties: list[dict[str, Any]]
    # 合规审查阶段输出的风险项
    audit_risks_found: list[dict[str, Any]]
    # 最终生成的 Markdown 摘要/报告
    final_audit_summary: str
    # 节点执行时的错误占位
    error_message: str
