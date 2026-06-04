from __future__ import annotations

import json
from pathlib import Path


OUTPUT_DIR = Path("data/labeling")
JSONL_OUTPUT_PATH = OUTPUT_DIR / "audit_risk_samples.jsonl"
LABEL_STUDIO_OUTPUT_PATH = OUTPUT_DIR / "audit_risk_samples_labelstudio.json"
SFT_OUTPUT_PATH = OUTPUT_DIR / "audit_risk_sft_demo.jsonl"

RISK_TYPES = [
    ("虚增收入", "收入确认政策与合同履约进度不匹配，期末集中确认大额收入。"),
    ("虚增利润", "毛利率显著高于同行，成本结转与收入规模不匹配。"),
    ("关联方利益输送", "客户与供应商存在共同股东或高管交叉任职。"),
    ("内控缺陷", "审批、验收和付款流程缺少关键复核记录。"),
    ("资金占用", "其他应收款长期挂账，交易对手与控股股东存在关联。"),
    ("存货跌价风险", "存货周转率下降且库龄结构异常，未充分计提跌价准备。"),
    ("应收账款坏账风险", "应收账款增长快于收入增长，逾期账款占比上升。"),
    ("信息披露不充分", "重大合同、关联交易或或有事项披露不完整。"),
]

COMPANIES = [
    "华辰智能装备股份有限公司",
    "海岳新材料有限公司",
    "星河医药科技股份有限公司",
    "北辰能源集团",
    "启明供应链管理有限公司",
    "东岭电子股份有限公司",
    "瑞泽环保科技有限公司",
    "远航商业保理有限公司",
]


def build_sample(index: int) -> dict:
    company = COMPANIES[index % len(COMPANIES)]
    risk_type, clue = RISK_TYPES[index % len(RISK_TYPES)]
    year = 2021 + index % 4
    revenue_growth = 18 + index % 47
    cashflow_drop = 7 + index % 31
    amount = 800 + (index * 137) % 9200
    severity = ["低", "中", "高"][index % 3]
    text = (
        f"{company}在{year}年度报告中披露营业收入同比增长{revenue_growth}%，"
        f"但经营活动现金流净额下降{cashflow_drop}%。审计抽样发现，"
        f"{clue} 涉及金额约{amount}万元，管理层解释为正常商业安排。"
    )
    return {
        "id": f"audit-sample-{index + 1:03d}",
        "text": text,
        "meta": {
            "company": company,
            "year": year,
            "risk_type": risk_type,
            "severity": severity,
            "source": "synthetic_demo_seed",
        },
    }


def build_sft_record(sample: dict) -> dict:
    return {
        "instruction": "请作为财务审计专家，识别文本中的主要审计风险类型、风险等级，并给出简要依据和整改建议。",
        "input": sample["text"],
        "output": (
            f"风险类型：{sample['meta']['risk_type']}\n"
            f"风险等级：{sample['meta']['severity']}\n"
            f"判断依据：文本显示{sample['meta']['company']}存在与该风险类型相关的异常审计线索，"
            "需要结合凭证、合同、现金流和关联方关系进一步复核。\n"
            "整改建议：补充底稿证据，执行穿透核查，复核收入、成本、往来款和关联交易披露，"
            "并形成管理层问询记录。"
        ),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = [build_sample(index) for index in range(200)]

    LABEL_STUDIO_OUTPUT_PATH.write_text(
        json.dumps(samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with JSONL_OUTPUT_PATH.open("w", encoding="utf-8") as sample_fp:
        for sample in samples:
            sample_fp.write(json.dumps(sample, ensure_ascii=False) + "\n")

    with SFT_OUTPUT_PATH.open("w", encoding="utf-8") as sft_fp:
        for sample in samples:
            sft_fp.write(json.dumps(build_sft_record(sample), ensure_ascii=False) + "\n")

    print(f"Wrote {LABEL_STUDIO_OUTPUT_PATH}")
    print(f"Wrote {JSONL_OUTPUT_PATH}")
    print(f"Wrote {SFT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
