from __future__ import annotations

import json
import urllib.request
from typing import Any

from .settings import ProjectSettings
from .state import AuditSystemState

# 本模块负责把审计结果整理成自动化系统可消费的结构化 payload，
# 当前默认对接 N8N，也支持在未配置 webhook 时返回 dry-run 结果用于演示。

def build_n8n_payload(state: AuditSystemState) -> dict[str, Any]:
    """Build the structured payload expected by the N8N audit workflow."""
    parsed = state.get("parsed_financial_data", {})
    risks = state.get("audit_risks_found", [])
    related_parties = state.get("discovered_related_parties", [])
    return {
        "company_name": parsed.get("company_name", "未知企业"),
        "reporting_year": parsed.get("reporting_year"),
        "risk_count": len(risks),
        "high_risk_count": sum(1 for risk in risks if risk.get("severity") == "高"),
        "risks": risks,
        "related_parties": related_parties,
        "final_audit_summary": state.get("final_audit_summary", ""),
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
        return {
            "sent": True,
            "status": response.status,
            "response": body,
        }
