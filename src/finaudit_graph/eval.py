from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .service import execute_audit


def run_eval(dataset_path: str | Path) -> dict[str, Any]:
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    cases = dataset.get("cases", [])
    results: list[dict[str, Any]] = []
    retrieval_hits = 0
    risk_hits = 0
    faithful_reports = 0

    for case in cases:
        result = execute_audit(case["document_path"])
        risks = result.get("audit_risks", [])
        risk_types = {item.get("risk_type") for item in risks}
        report = result.get("final_report_markdown", "")

        expected_risks = set(case.get("expected_risk_types", []))
        expected_keywords = set(case.get("expected_report_keywords", []))

        case_risk_hit = len(expected_risks & risk_types)
        case_retrieval_hit = 1 if case.get("expected_rag_ids") else 0
        case_faithful = all(keyword in report for keyword in expected_keywords)

        retrieval_hits += case_retrieval_hit
        risk_hits += case_risk_hit
        faithful_reports += 1 if case_faithful else 0

        results.append(
            {
                "case_id": case["case_id"],
                "document_path": case["document_path"],
                "risk_hit_count": case_risk_hit,
                "expected_risk_count": len(expected_risks),
                "report_faithful": case_faithful,
                "identified_risks": sorted(risk_types),
            }
        )

    total_cases = len(cases) or 1
    total_expected_risks = sum(len(case.get("expected_risk_types", [])) for case in cases) or 1
    return {
        "dataset_path": str(dataset_path),
        "case_count": len(cases),
        "retrieval_hit_rate": round(retrieval_hits / total_cases, 4),
        "risk_recall": round(risk_hits / total_expected_risks, 4),
        "report_faithfulness": round(faithful_reports / total_cases, 4),
        "results": results,
    }
