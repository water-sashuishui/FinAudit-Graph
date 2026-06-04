from __future__ import annotations

from collections.abc import Callable

from .nodes import (
    node_compliance_checker,
    node_data_parser,
    node_graph_searcher,
    node_report_generator,
)
from .state import AuditSystemState


class SequentialAuditWorkflow:
    """Fallback workflow used when LangGraph is not installed yet."""

    def __init__(self, nodes: list[Callable[[AuditSystemState], AuditSystemState]]) -> None:
        self._nodes = nodes

    def invoke(self, initial_state: AuditSystemState) -> AuditSystemState:
        state = initial_state
        for node in self._nodes:
            state = node(state)
        return state


def build_audit_workflow():
    """Compile the FinAudit-Graph workflow.

    The preferred path uses LangGraph. The fallback keeps the demo runnable in
    minimal environments and mirrors the same node order.
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return SequentialAuditWorkflow(
            [
                node_data_parser,
                node_graph_searcher,
                node_compliance_checker,
                node_report_generator,
            ]
        )

    workflow = StateGraph(AuditSystemState)
    workflow.add_node("node_data_parser", node_data_parser)
    workflow.add_node("node_graph_searcher", node_graph_searcher)
    workflow.add_node("node_compliance_checker", node_compliance_checker)
    workflow.add_node("node_report_generator", node_report_generator)

    workflow.set_entry_point("node_data_parser")
    workflow.add_edge("node_data_parser", "node_graph_searcher")
    workflow.add_edge("node_graph_searcher", "node_compliance_checker")
    workflow.add_edge("node_compliance_checker", "node_report_generator")
    workflow.add_edge("node_report_generator", END)
    return workflow.compile()


def run_demo(raw_document_path: str = "data/raw/demo_annual_report.pdf") -> AuditSystemState:
    graph = build_audit_workflow()
    return graph.invoke({"raw_document_path": raw_document_path})

