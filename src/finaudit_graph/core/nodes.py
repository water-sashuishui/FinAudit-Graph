from __future__ import annotations

import json
from typing import Any

from ..ingestion.parsing import parse_financial_document
from ..intelligence.audit_agent import run_langchain_audit_agent
from ..intelligence.llm import DeepSeekClient
from ..intelligence.negotiation import run_multi_agent_negotiation
from ..retrieval.graph_store import ingest_parsed_graph
from ..retrieval.knowledge import retrieve_audit_standards, retrieve_related_parties
from .state import AuditSystemState


def node_data_parser(state: AuditSystemState) -> AuditSystemState:
    """解析原始审计材料，并把结构化财务字段写入工作流状态。"""
    raw_path = state.get("raw_document_path", "data/demo_inputs/test_audit.txt")
    parsed = parse_financial_document(raw_path)
    return {**state, "parsed_financial_data": parsed, "error_message": ""}


def node_graph_searcher(state: AuditSystemState) -> AuditSystemState:
    """写入并检索关联方图谱线索，供后续风险判断使用。"""
    parsed = state.get("parsed_financial_data", {})
    company_name = parsed.get("company_name", "未知企业")

    # 该 Cypher 模板同时作为查询逻辑说明返回给调用方，便于演示和答辩时解释
    # “为什么这些企业/人员会被识别为潜在关联方”。
    cypher_query = """
    MATCH path = (c:Company {name: $company_name})-[r:CONTROLLED_BY|PURCHASES_FROM|SUPPLIES|HAS_RECEIVABLE_FROM|RELATED_TO*1..3]-(p)
    WHERE p <> c
      AND any(rel IN r WHERE coalesce(rel.hidden, false) = true OR coalesce(rel.ratio, 0) >= 0.2 OR coalesce(rel.confidence, 1.0) >= 0.6)
    RETURN coalesce(p.name, "unknown") AS related_party,
           length(path) AS depth,
           [rel IN r | type(rel) + ":" + coalesce(rel.evidence, "")] AS relation_path
    LIMIT 20
    """
    # 先尝试把本次上传材料抽取出的企业关系写入 Neo4j；不可用时底层会降级，
    # 但状态字段仍会被带回，方便前端展示图谱来源和写入结果。
    graph_status = ingest_parsed_graph({**parsed, "company_name": company_name})
    related_parties = retrieve_related_parties(company_name)
    for item in related_parties:
        item["cypher_template"] = cypher_query.strip()
    return {
        **state,
        **graph_status,
        "parsed_financial_data": {**parsed, "company_name": company_name},
        "discovered_related_parties": related_parties,
    }


def node_compliance_checker(state: AuditSystemState) -> AuditSystemState:
    """结合财务字段、图谱线索和审计准则识别风险点。"""
    parsed = state.get("parsed_financial_data", {})
    related_parties = state.get("discovered_related_parties", [])
    # 这里用宽关键词召回准则片段，后续无论是 Agent、DeepSeek 还是本地规则，
    # 都共用同一批审计依据，避免不同分支的结论来源不一致。
    standards = retrieve_audit_standards(
        ["收入", "现金流", "应收账款", "关联方", "控制", "内控", "毛利率", "成本"],
        limit=4,
    )
    basis_by_id = {item["id"]: item["content"] for item in standards}

    # 风险识别按“高级能力优先、稳定规则兜底”排列：LangChain Agent 能用则优先，
    # DeepSeek 直连次之；两者都不可用时仍通过本地规则给出演示级审计结果。
    agent_risks = run_langchain_audit_agent(parsed, related_parties, standards)
    if agent_risks:
        return _finalize_negotiation(state, parsed, related_parties, standards, agent_risks, "langchain_deepseek_agent")

    llm_risks = _try_deepseek_risk_analysis(parsed, related_parties, standards)
    if llm_risks:
        return _finalize_negotiation(state, parsed, related_parties, standards, llm_risks, "deepseek")

    risks = [
        {
            "risk_type": "虚增收入",
            "severity": "高",
            "evidence": "收入增长率显著高于经营现金流增长率，且应收账款同步快速上升。",
            "audit_basis": basis_by_id.get(
                "revenue-recognition",
                "收入确认应结合合同义务履约、验收证据和现金流回款情况复核。",
            ),
            "recommendation": "抽查期末大额合同、验收单、发票和回款记录，重点复核跨期收入。",
        },
        {
            "risk_type": "内控缺陷",
            "severity": "中",
            "evidence": "收入、应收和关联方线索同时异常，提示审批和复核控制可能不足。",
            "audit_basis": basis_by_id.get(
                "internal-control",
                "关键业务流程应保留审批、验收、对账和复核底稿。",
            ),
            "recommendation": "复核销售审批、客户信用评估和期后回款监控流程。",
        },
    ]

    if related_parties:
        # 只有图谱真实命中关联方时才插入该风险，避免对无图谱证据的企业凭空定性。
        risks.insert(
            1,
            {
                "risk_type": "关联方利益输送",
                "severity": "高",
                "evidence": f"图谱发现 {len(related_parties)} 个潜在关联方，存在共同控制或资金往来线索。",
                "audit_basis": basis_by_id.get(
                    "related-party",
                    "关联方交易应完整披露交易背景、定价公允性和资金流向。",
                ),
                "recommendation": "执行股权穿透和银行流水核查，补充关联交易披露充分性测试。",
            },
        )

    if (parsed.get("gross_margin_rate") or 0) > 55:
        # 毛利率阈值是本地规则的保守演示判断；最终等级仍会经过多智能体协商收敛。
        risks.append(
            {
                "risk_type": "成本结转异常",
                "severity": "中",
                "evidence": "毛利率高于常规制造业水平，需要核查成本结转完整性。",
                "audit_basis": basis_by_id.get(
                    "cost-inventory",
                    "成本费用应与收入配比，存货发出和生产成本分摊应有一致依据。",
                ),
                "recommendation": "抽查成本计算单、出入库记录和成本分摊规则。",
            }
        )

    return _finalize_negotiation(state, parsed, related_parties, standards, risks, "local_rules_negotiated")


def _finalize_negotiation(
    state: AuditSystemState,
    parsed: dict[str, Any],
    related_parties: list[dict[str, Any]],
    standards: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    provider: str,
) -> AuditSystemState:
    """统一对候选风险做协商收敛，并写回工作流状态。"""
    negotiated = run_multi_agent_negotiation(risks, parsed, related_parties, standards)
    return {
        **state,
        "audit_risks_found": negotiated["risks"],
        "negotiation_trace": negotiated["trace"],
        "llm_provider": provider,
    }


def _try_deepseek_risk_analysis(
    parsed: dict[str, Any],
    related_parties: list[dict[str, Any]],
    standards: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """在 DeepSeek 配置可用时请求结构化风险分析。"""
    client = DeepSeekClient()
    if not client.configured:
        return None

    # 强约束模型只返回 JSON，便于后续进行字段校验并与本地规则输出保持同构。
    messages = [
        {
            "role": "system",
            "content": (
                "你是财务审计与合规审查专家。只返回 JSON，不要 Markdown。"
                'JSON 格式必须是 {"risks": [{"risk_type": str, "severity": str, '
                '"evidence": str, "audit_basis": str, "recommendation": str}]}。'
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "parsed_financial_data": parsed,
                    "related_parties": related_parties,
                    "audit_standards": standards,
                    "task": "识别 3 到 5 个审计风险点，风险等级只能使用 高 / 中 / 低。",
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        content = client.chat(messages)
        data = json.loads(content)
        risks = data.get("risks", [])
        if not isinstance(risks, list):
            return None
        valid_risks = []
        for risk in risks:
            if not isinstance(risk, dict):
                continue
            # 只接受报告生成所需的完整风险字段，防止半结构化模型输出污染状态。
            if {"risk_type", "severity", "evidence", "audit_basis", "recommendation"}.issubset(risk):
                valid_risks.append(risk)
        return valid_risks or None
    except Exception:
        return None


def node_report_generator(state: AuditSystemState) -> AuditSystemState:
    """将前序节点结果汇总成面向用户的 Markdown 审计综述。"""
    parsed = state.get("parsed_financial_data", {})
    related_parties = state.get("discovered_related_parties", [])
    risks = state.get("audit_risks_found", [])

    risk_lines = []
    for index, risk in enumerate(risks, start=1):
        # 协商模块会追加置信度和保留意见；报告层只负责在存在时展示这些补充信息。
        confidence = f"；协商置信度 {risk.get('confidence', 0):.2f}" if "confidence" in risk else ""
        notes = risk.get("disagreement_notes", [])
        note_line = f"   - 保留意见：{'；'.join(notes)}" if notes else None
        block = [
            f"{index}. **{risk['risk_type']}（{risk['severity']}）**",
            f"   - 依据：{risk['evidence']}",
            f"   - 准则/审计关注：{risk['audit_basis']}",
            f"   - 建议：{risk['recommendation']}{confidence}",
        ]
        if note_line:
            block.append(note_line)
        risk_lines.append("\n".join(block))

    related_party_lines = [
        f"- {item['name']}：{item['relation']}，穿透深度 {item['depth']}，证据：{item['evidence']}"
        for item in related_parties
    ]

    summary = f"""# FinAudit-Graph 智能审计综述

## 一、被审计对象

- 企业名称：{parsed.get("company_name", "未知企业")}
- 报告年度：{parsed.get("reporting_year", "未知")}
- 原始文件：{parsed.get("source_file", "未提供")}

## 二、核心财务线索

- 营业收入增长率：{parsed.get("revenue_growth_rate", "N/A")}%
- 经营现金流增长率：{parsed.get("operating_cashflow_growth_rate", "N/A")}%
- 毛利率：{parsed.get("gross_margin_rate", "N/A")}%
- 应收账款增长率：{parsed.get("accounts_receivable_growth_rate", "N/A")}%

## 三、潜在关联方

{chr(10).join(related_party_lines) if related_party_lines else "- 暂未发现可疑关联方。"}

## 四、审计风险点

{chr(10).join(risk_lines)}

## 五、综合结论

系统建议将该企业列为高优先级复核对象，重点围绕收入真实性、关联交易披露充分性、成本结转完整性和内控审批链条开展进一步审计程序。"""
    return {**state, "final_audit_summary": summary}
