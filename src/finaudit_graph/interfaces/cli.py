from __future__ import annotations

import argparse
import json

from ..core.service import execute_audit, query_audit_standards, rebuild_rag_index
from ..evaluation.eval import run_eval
from ..intelligence.lora import inspect_lora_artifact
from ..settings import ProjectSettings


def main() -> None:
    """命令行入口：按参数选择演示审计、RAG、LoRA 摘要或本地评估任务。"""
    parser = argparse.ArgumentParser(description="FinAudit-Graph command line tools")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the four-node audit workflow demo and print the Markdown report.",
    )
    parser.add_argument(
        "--document",
        default="data/demo_inputs/test_audit.txt",
        help="Path to a source audit document used by the demo workflow.",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save Markdown and optional DOCX reports into the data/outputs directory.",
    )
    parser.add_argument(
        "--lora-summary",
        action="store_true",
        help="Print the exported LoRA adapter summary.",
    )
    parser.add_argument(
        "--build-rag-index",
        action="store_true",
        help="Build the local persistent vector database for audit-standard RAG.",
    )
    parser.add_argument(
        "--rag-query",
        help="Search the local audit-standard vector database with a natural-language query.",
    )
    parser.add_argument(
        "--run-eval",
        action="store_true",
        help="Run the local evaluation dataset and print metrics.",
    )
    parser.add_argument(
        "--eval-dataset",
        default="data/eval_dataset.json",
        help="Path to the local evaluation dataset JSON file.",
    )
    args = parser.parse_args()

    # CLI 只做参数分发；真实业务逻辑都复用 service/eval/lora 等模块，避免入口间逻辑漂移。
    settings = ProjectSettings.from_env()
    if args.lora_summary:
        print(json.dumps(inspect_lora_artifact(), ensure_ascii=False, indent=2))
        return

    if args.build_rag_index:
        print(json.dumps(rebuild_rag_index(), ensure_ascii=False, indent=2))
        return

    if args.rag_query:
        print(json.dumps(query_audit_standards(args.rag_query, limit=5), ensure_ascii=False, indent=2))
        return

    if args.run_eval:
        print(json.dumps(run_eval(args.eval_dataset), ensure_ascii=False, indent=2))
        return

    if args.demo:
        result = execute_audit(args.document, save_report=args.save_report)
        print(result["final_report_markdown"])
        if args.save_report and "report_paths" in result:
            paths = result["report_paths"]
            print(f"Saved Markdown report: {paths['markdown']}")
            if paths["docx"]:
                print(f"Saved DOCX report: {paths['docx']}")
        return

    print("FinAudit-Graph local tooling is ready.")
    print(f"Neo4j URI: {settings.neo4j_uri}")
    print("Next step: run `python -m finaudit_graph --demo` to test the workflow.")
