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
    """LangGraph 不可用时的最小工作流适配器。

    对外保留与 LangGraph compiled graph 一致的 ``invoke`` 方法，方便服务层
    和测试代码不关心当前运行环境是否安装了 LangGraph。
    """

    def __init__(self, nodes: list[Callable[[AuditSystemState], AuditSystemState]]) -> None:
        """保存按顺序执行的节点列表。"""
        self._nodes = nodes

    def invoke(self, initial_state: AuditSystemState) -> AuditSystemState:
        """按 LangGraph invoke 兼容接口顺序执行所有节点。"""
        state = initial_state
        for node in self._nodes:
            state = node(state)
        return state


def build_audit_workflow():
    """构建 FinAudit-Graph 的四阶段审计工作流。

    优先使用 LangGraph 表达节点和边；如果演示环境未安装 LangGraph，则回退到
    同顺序的串行执行器，确保核心链路仍可运行。
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        # 没有安装 LangGraph 时，仍按同样的节点顺序串行执行，保证 MVP 可跑。
        return SequentialAuditWorkflow(
            [
                node_data_parser,
                node_graph_searcher,
                node_compliance_checker,
                node_report_generator,
            ]
        )

    workflow = StateGraph(AuditSystemState)
    # 四个节点分别负责：材料解析、图谱线索检索、风险判断、报告生成。
    workflow.add_node("node_data_parser", node_data_parser)
    workflow.add_node("node_graph_searcher", node_graph_searcher)
    workflow.add_node("node_compliance_checker", node_compliance_checker)
    workflow.add_node("node_report_generator", node_report_generator)

    # 节点之间只通过 AuditSystemState 传递数据，避免在节点内部隐藏跨阶段依赖。
    workflow.set_entry_point("node_data_parser")
    workflow.add_edge("node_data_parser", "node_graph_searcher")
    workflow.add_edge("node_graph_searcher", "node_compliance_checker")
    workflow.add_edge("node_compliance_checker", "node_report_generator")
    workflow.add_edge("node_report_generator", END)
    return workflow.compile()


def run_demo(raw_document_path: str = "data/demo_inputs/test_audit.txt") -> AuditSystemState:
    """使用指定材料路径运行演示工作流，并返回完整状态。"""
    # demo 入口只准备初始状态；具体执行顺序由 build_audit_workflow 统一维护。
    graph = build_audit_workflow()
    return graph.invoke({"raw_document_path": raw_document_path})
