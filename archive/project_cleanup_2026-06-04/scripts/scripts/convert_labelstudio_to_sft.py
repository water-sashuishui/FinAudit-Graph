from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/labeling/project-36-at-2026-06-03-12-03-06025e56.json")
DEFAULT_OUTPUT = Path("data/processed/audit_risk_sft_from_labelstudio_30.jsonl")
DEFAULT_SUMMARY = Path("data/processed/labelstudio_export_summary.json")


def extract_annotation(task: dict[str, Any]) -> dict[str, Any]:
    annotations = task.get("annotations") or []
    if not annotations:
        return {
            "risk_type": "",
            "entities": [],
        }

    result = annotations[0].get("result", [])
    risk_type = ""
    entities: list[dict[str, Any]] = []

    for item in result:
        value = item.get("value", {})
        choices = value.get("choices") or []
        labels = value.get("labels") or []
        if choices:
            risk_type = choices[0]
        if labels:
            entities.append(
                {
                    "label": labels[0],
                    "text": value.get("text", ""),
                    "start": value.get("start"),
                    "end": value.get("end"),
                }
            )

    return {
        "risk_type": risk_type,
        "entities": entities,
    }


def group_entities(entities: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for entity in entities:
        label = entity.get("label", "其他")
        text = entity.get("text", "")
        if text:
            grouped.setdefault(label, []).append(text)
    return grouped


def build_output(task: dict[str, Any]) -> dict[str, str]:
    data = task["data"]
    meta = data.get("meta", {})
    annotation = extract_annotation(task)
    grouped = group_entities(annotation["entities"])

    risk_type = annotation["risk_type"] or meta.get("risk_type", "未标注")
    severity = meta.get("severity", "中")
    company = meta.get("company", "未知企业")
    amount = "、".join(grouped.get("涉案金额", [])) or "未标注"
    indicators = "、".join(grouped.get("关键财务指标", [])) or "未标注"
    abnormal_clues = "、".join(grouped.get("异常审计表现", [])) or "未标注"
    defense = "、".join(grouped.get("管理层抗辩理由", [])) or "未标注"

    return {
        "instruction": "请作为财务审计专家，根据审计文本和人工标注线索，识别主要审计风险类型、风险等级，并给出判断依据和整改建议。",
        "input": data["text"],
        "output": (
            f"风险类型：{risk_type}\n"
            f"风险等级：{severity}\n"
            f"涉及企业：{company}\n"
            f"关键财务指标：{indicators}\n"
            f"异常审计表现：{abnormal_clues}\n"
            f"涉案金额：{amount}\n"
            f"管理层抗辩理由：{defense}\n"
            "判断依据：该文本存在人工标注的异常审计表现和关键财务指标波动，需要结合合同、凭证、现金流、往来款和关联方关系进一步复核。\n"
            "整改建议：补充审计底稿证据，执行穿透核查和截止性测试，复核交易真实性、定价公允性、资金流向及信息披露完整性。"
        ),
    }


def convert(input_path: Path, output_path: Path, summary_path: Path) -> None:
    tasks = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    risk_counter: Counter[str] = Counter()
    label_counter: Counter[str] = Counter()
    converted = 0

    with output_path.open("w", encoding="utf-8") as fp:
        for task in tasks:
            annotation = extract_annotation(task)
            if not annotation["risk_type"]:
                continue
            for entity in annotation["entities"]:
                label_counter[entity["label"]] += 1
            risk_counter[annotation["risk_type"]] += 1
            fp.write(json.dumps(build_output(task), ensure_ascii=False) + "\n")
            converted += 1

    summary = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "task_count": len(tasks),
        "converted_count": converted,
        "risk_type_counts": dict(risk_counter),
        "entity_label_counts": dict(label_counter),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Label Studio export to SFT JSONL.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    convert(args.input, args.output, args.summary)


if __name__ == "__main__":
    main()
