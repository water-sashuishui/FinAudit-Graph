from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"低": 1, "中": 2, "高": 3}
DEFAULT_CONFIDENCE = 0.6


def run_multi_agent_negotiation(
    risks: list[dict[str, Any]],
    parsed: dict[str, Any],
    related_parties: list[dict[str, Any]],
    standards: list[dict[str, Any]],
    max_rounds: int = 2,
) -> dict[str, Any]:
    """Run a bounded, structured negotiation over risk items."""
    normalized = [_normalize_risk(risk) for risk in risks]
    trace: list[dict[str, Any]] = []
    current = normalized

    for round_index in range(1, max_rounds + 1):
        proposals = _collect_round_proposals(round_index, current, parsed, related_parties, standards)
        if not proposals:
            break
        trace.extend(proposals)
        current = _adjudicate(current, proposals)
        if not _needs_followup(current, round_index, max_rounds):
            break

    return {"risks": current, "trace": trace, "rounds": max_rounds}


def _collect_round_proposals(
    round_index: int,
    risks: list[dict[str, Any]],
    parsed: dict[str, Any],
    related_parties: list[dict[str, Any]],
    standards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for risk in risks:
        proposals.extend(_risk_agent_review(round_index, risk, parsed, related_parties))
        proposals.extend(_evidence_agent_review(round_index, risk, related_parties, standards))
        proposals.extend(_recommendation_agent_review(round_index, risk))
    return proposals


def _risk_agent_review(
    round_index: int,
    risk: dict[str, Any],
    parsed: dict[str, Any],
    related_parties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    risk_name = str(risk.get("risk_type", ""))
    revenue = float(parsed.get("revenue_growth_rate") or 0)
    cashflow = float(parsed.get("operating_cashflow_growth_rate") or 0)
    gross_margin = float(parsed.get("gross_margin_rate") or 0)

    if "收入" in risk_name and revenue > 25 and cashflow < 0 and risk.get("severity") != "高":
        proposals.append(
            _proposal(
                "RiskAgent",
                round_index,
                risk_name,
                "raise_severity",
                suggested_severity="高",
                confidence_delta=0.1,
                disagreement_note="收入与现金流背离，风险等级应从严。",
            )
        )
    if "关联方" in risk_name and related_parties and risk.get("severity") != "高":
        proposals.append(
            _proposal(
                "RiskAgent",
                round_index,
                risk_name,
                "raise_severity",
                suggested_severity="高",
                confidence_delta=0.1,
                disagreement_note="已发现关联方线索，关联交易风险不应低估。",
            )
        )
    if "成本" in risk_name and gross_margin > 55 and risk.get("severity") == "低":
        proposals.append(
            _proposal(
                "RiskAgent",
                round_index,
                risk_name,
                "raise_severity",
                suggested_severity="中",
                confidence_delta=0.05,
                disagreement_note="高毛利率异常时，成本结转风险至少保持中等关注。",
            )
        )
    return proposals


def _evidence_agent_review(
    round_index: int,
    risk: dict[str, Any],
    related_parties: list[dict[str, Any]],
    standards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    risk_name = str(risk.get("risk_type", ""))
    evidence = str(risk.get("evidence", "")).strip()
    audit_basis = str(risk.get("audit_basis", "")).strip()

    if len(evidence) < 12:
        proposals.append(
            _proposal(
                "EvidenceAgent",
                round_index,
                risk_name,
                "lower_confidence",
                confidence_delta=-0.2,
                disagreement_note="风险依据过短，证据充分性不足。",
            )
        )
    if len(audit_basis) < 12:
        proposals.append(
            _proposal(
                "EvidenceAgent",
                round_index,
                risk_name,
                "lower_confidence",
                confidence_delta=-0.2,
                disagreement_note="审计依据不足，建议补充准则引用。",
            )
        )
    elif standards:
        proposals.append(
            _proposal(
                "EvidenceAgent",
                round_index,
                risk_name,
                "raise_confidence",
                confidence_delta=0.1,
            )
        )
    if "关联方" in risk_name and not related_parties:
        proposals.append(
            _proposal(
                "EvidenceAgent",
                round_index,
                risk_name,
                "lower_confidence",
                confidence_delta=-0.15,
                disagreement_note="未检出关联方图谱线索，关联方风险需要保留意见。",
            )
        )
    return proposals


def _recommendation_agent_review(round_index: int, risk: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    risk_name = str(risk.get("risk_type", ""))
    recommendation = str(risk.get("recommendation", "")).strip()

    if len(recommendation) < 12:
        proposals.append(
            _proposal(
                "RecommendationAgent",
                round_index,
                risk_name,
                "patch_recommendation",
                confidence_delta=-0.05,
                proposed_recommendation="补充执行底稿抽查、原始单据复核和关键流程穿行测试。",
                disagreement_note="整改建议过于笼统，已补充可执行动作。",
            )
        )
    return proposals


def _adjudicate(risks: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proposal_map: dict[str, list[dict[str, Any]]] = {}
    for proposal in proposals:
        proposal_map.setdefault(proposal["risk_type"], []).append(proposal)

    negotiated: list[dict[str, Any]] = []
    for risk in risks:
        current = dict(risk)
        current.setdefault("confidence", DEFAULT_CONFIDENCE)
        notes = list(current.get("disagreement_notes", []))
        consulted = set(current.get("consulted_agents", []))
        risk_proposals = proposal_map.get(current["risk_type"], [])

        for proposal in risk_proposals:
            consulted.add(proposal["reviewer"])
            if proposal.get("suggested_severity"):
                current["severity"] = _max_severity(current["severity"], proposal["suggested_severity"])
            current["confidence"] = round(
                min(0.99, max(0.05, float(current.get("confidence", DEFAULT_CONFIDENCE)) + proposal["confidence_delta"])),
                2,
            )
            if proposal.get("proposed_recommendation") and len(str(current.get("recommendation", "")).strip()) < 12:
                current["recommendation"] = proposal["proposed_recommendation"]
            if proposal.get("disagreement_note"):
                notes.append(proposal["disagreement_note"])

        current["disagreement_notes"] = _unique_list(notes)
        current["consulted_agents"] = sorted(consulted)
        current["negotiation_status"] = "resolved" if current["confidence"] >= 0.5 else "needs_manual_review"
        negotiated.append(current)
    return negotiated


def _needs_followup(risks: list[dict[str, Any]], round_index: int, max_rounds: int) -> bool:
    if round_index >= max_rounds:
        return False
    return any(risk.get("confidence", DEFAULT_CONFIDENCE) < 0.7 for risk in risks)


def _normalize_risk(risk: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(risk)
    normalized.setdefault("confidence", DEFAULT_CONFIDENCE)
    normalized.setdefault("disagreement_notes", [])
    normalized.setdefault("consulted_agents", [])
    normalized.setdefault("negotiation_status", "pending")
    return normalized


def _proposal(
    reviewer: str,
    round_index: int,
    risk_type: str,
    action: str,
    *,
    suggested_severity: str | None = None,
    confidence_delta: float = 0.0,
    proposed_recommendation: str | None = None,
    disagreement_note: str | None = None,
) -> dict[str, Any]:
    return {
        "reviewer": reviewer,
        "round": round_index,
        "risk_type": risk_type,
        "action": action,
        "suggested_severity": suggested_severity,
        "confidence_delta": confidence_delta,
        "proposed_recommendation": proposed_recommendation,
        "disagreement_note": disagreement_note,
    }


def _max_severity(left: str, right: str) -> str:
    return left if SEVERITY_ORDER.get(left, 0) >= SEVERITY_ORDER.get(right, 0) else right


def _unique_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
