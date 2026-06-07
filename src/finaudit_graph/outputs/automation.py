from __future__ import annotations

import json
import urllib.request
from typing import Any

from ..core.state import AuditSystemState
from ..settings import ProjectSettings

# 本模块负责把审计结果整理成自动化系统可消费的结构化 payload，
# 当前默认对接 N8N，也支持在未配置 webhook 时返回 dry-run 结果用于演示。

def build_n8n_payload(state: AuditSystemState) -> dict[str, Any]:
    """Build the structured payload expected by the N8N audit workflow."""
    settings = ProjectSettings.from_env()
    parsed = state.get("parsed_financial_data", {})
    risks = state.get("audit_risks_found", [])
    related_parties = state.get("discovered_related_parties", [])
    company_name = parsed.get("company_name", "未知企业")
    reporting_year = parsed.get("reporting_year")
    high_risk_count = sum(1 for risk in risks if risk.get("severity") == "高")
    risk_lines = [
        f"- {risk.get('risk_type', '未知风险')}（{risk.get('severity', '未知')}）：{risk.get('evidence', '')}"
        for risk in risks
    ]
    return {
        "company_name": company_name,
        "reporting_year": reporting_year,
        "risk_count": len(risks),
        "high_risk_count": high_risk_count,
        "risks": risks,
        "related_parties": related_parties,
        "final_audit_summary": state.get("final_audit_summary", ""),
        "review_email": settings.audit_review_email,
        "email_subject": f"FinAudit-Graph 审计复核提醒：{company_name}（{reporting_year}）",
        "email_body": "\n".join(
            [
                "FinAudit-Graph 已完成一份审计分析，请关注以下复核线索。",
                "",
                f"被审计单位：{company_name}",
                f"报告年度：{reporting_year}",
                f"风险总数：{len(risks)}",
                f"高风险数量：{high_risk_count}",
                "",
                "风险摘要：",
                *(risk_lines or ["- 暂未识别到审计风险。"]),
                "",
                "请登录系统查看完整审计报告和底稿证据。",
            ]
        ),
    }


def send_to_n8n(payload: dict[str, Any], settings: ProjectSettings | None = None) -> dict[str, Any]:
    """Send audit result to N8N, or return a dry-run response if no webhook is configured."""
    settings = settings or ProjectSettings.from_env()
    if not settings.n8n_webhook_url:
        # 未配置真实 webhook 时不报错，直接把 payload 原样回显给前端和 CLI。
        return {
            "sent": False,
            "mode": "dry_run",
            "message": "N8N_WEBHOOK_URL is not configured; payload was not sent.",
            "payload": payload,
        }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        settings.n8n_webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
        return normalize_n8n_response(response.status, body)


def normalize_n8n_response(status: int, body: str) -> dict[str, Any]:
    """Normalize N8N webhook response into stable API/frontend fields."""
    result: dict[str, Any] = {
        "sent": 200 <= status < 300,
        "status": status,
        "mode": "webhook_response",
        "message": body.strip() or "N8N webhook completed.",
        "response": body,
    }
    try:
        parsed = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        return result

    if isinstance(parsed, dict):
        result["response_json"] = parsed
        if "sent" in parsed:
            result["sent"] = bool(parsed["sent"])
        if parsed.get("mode"):
            result["mode"] = str(parsed["mode"])
        if parsed.get("message"):
            result["message"] = str(parsed["message"])
    return result
