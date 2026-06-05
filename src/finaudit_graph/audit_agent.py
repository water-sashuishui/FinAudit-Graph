from __future__ import annotations

import json
from typing import Any

from .settings import ProjectSettings


REQUIRED_RISK_FIELDS = {"risk_type", "severity", "evidence", "audit_basis", "recommendation"}


def create_deepseek_audit_agent(settings: ProjectSettings | None = None):
    """Create a LangChain 1.x agent backed by DeepSeek's OpenAI-compatible API."""
    settings = settings or ProjectSettings.from_env()
    if not settings.deepseek_api_key or not settings.audit_llm_model:
        return None

    try:
        from langchain.agents import create_agent
        from langchain_core.tools import tool
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    @tool
    def financial_metrics_tool(metrics_json: str) -> str:
        """Analyze financial metrics and return audit concern clues."""
        try:
            metrics = json.loads(metrics_json)
        except json.JSONDecodeError:
            return "无法解析财务指标 JSON。"

        # 这个工具只做“指标异常解释”，不直接生成最终风险 JSON。
        clues = []
        revenue = float(metrics.get("revenue_growth_rate") or 0)
        cashflow = float(metrics.get("operating_cashflow_growth_rate") or 0)
        gross_margin = float(metrics.get("gross_margin_rate") or 0)
        receivable = float(metrics.get("accounts_receivable_growth_rate") or 0)
        if revenue > 25 and cashflow < 0:
            clues.append("收入增长与经营现金流背离，关注收入真实性和截止性。")
        if receivable > 30:
            clues.append("应收账款增长较快，关注回款和坏账风险。")
        if gross_margin > 55:
            clues.append("毛利率偏高，关注成本结转和存货计价。")
        return "\n".join(clues) or "未发现显著财务指标异常。"

    @tool
    def rag_retriever_tool(query: str) -> str:
        """Retrieve audit standards from the local vector database."""
        from .knowledge import retrieve_audit_standards

        # Agent 不直接接触底层向量库实现，只通过这个工具取回可解释的准则片段。
        standards = retrieve_audit_standards([query], limit=4)
        return json.dumps(standards, ensure_ascii=False)

    @tool
    def related_party_tool(related_parties_json: str) -> str:
        """Summarize related-party graph clues."""
        try:
            parties = json.loads(related_parties_json)
        except json.JSONDecodeError:
            return "无法解析关联方 JSON。"
        if not parties:
            return "暂未发现可疑关联方。"
        return json.dumps(parties, ensure_ascii=False)

    model = ChatOpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.audit_llm_model,
        temperature=0.2,
    )
    return create_agent(
        model=model,
        tools=[financial_metrics_tool, rag_retriever_tool, related_party_tool],
        # 这里把输出格式约束死，尽量减少 Agent 返回自然语言造成的解析失败。
        system_prompt=(
            "你是财务审计 LangChain Agent。你必须先根据需要调用工具，再输出 JSON。"
            "只返回 JSON，不要 Markdown。格式为 "
            "{\"risks\":[{\"risk_type\":str,\"severity\":str,"
            "\"evidence\":str,\"audit_basis\":str,\"recommendation\":str}]}。"
            "风险等级只能使用 高/中/低。"
        ),
        name="deepseek_audit_agent",
    )


def run_langchain_audit_agent(
    parsed: dict[str, Any],
    related_parties: list[dict[str, Any]],
    standards: list[dict[str, Any]],
    agent_executor: Any | None = None,
    settings: ProjectSettings | None = None,
) -> list[dict[str, Any]] | None:
    """Run the LangChain Agent and return validated audit risks."""
    agent = agent_executor if agent_executor is not None else create_deepseek_audit_agent(settings)
    if agent is None:
        return None

    # 预取到的结构化信息统一打包给 Agent，减少它在工具之外的自由猜测空间。
    prompt_payload = {
        "parsed_financial_data": parsed,
        "related_parties": related_parties,
        "prefetched_audit_standards": standards,
        "instructions": [
            "调用 financial_metrics_tool 分析财务指标。",
            "调用 rag_retriever_tool 检索审计准则。",
            "调用 related_party_tool 判断关联方线索。",
            "综合工具结果输出 2 到 5 个审计风险 JSON。",
        ],
    }
    try:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(prompt_payload, ensure_ascii=False),
                    }
                ]
            }
        )
        content = _last_message_content(result)
        data = json.loads(_strip_json_fence(content))
        risks = data.get("risks", [])
        if not isinstance(risks, list):
            return None
        # 只保留满足固定字段集合的风险项，后端其余部分才能稳定消费。
        valid = [risk for risk in risks if isinstance(risk, dict) and REQUIRED_RISK_FIELDS.issubset(risk)]
        return valid or None
    except Exception:
        return None


def _last_message_content(result: Any) -> str:
    """从 LangChain invoke 结果中提取最后一条消息文本。"""
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if not messages:
        return ""
    message = messages[-1]
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    return str(content or "")


def _strip_json_fence(content: str) -> str:
    """去掉模型可能包裹的 ```json 代码块，只保留 JSON 文本。"""
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()
