from __future__ import annotations

import argparse
import json

from .lora import inspect_lora_artifact
from .settings import ProjectSettings
from .reporting import build_full_report_markdown, save_reports
from .workflow import run_demo
from .knowledge import AUDIT_STANDARD_PATH, retrieve_audit_standards
from .vector_store import DEFAULT_VECTOR_STORE_PATH, LocalVectorStore


def main() -> None:
    """Run project readiness checks or the audit workflow demo."""
    parser = argparse.ArgumentParser(description="FinAudit-Graph command line tools")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the four-node audit workflow demo and print the Markdown report.",
    )
    parser.add_argument(
        "--document",
        default="data/raw/demo_annual_report.pdf",
        help="Path to a source audit document used by the demo workflow.",
    )
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save Markdown and optional DOCX reports into the outputs directory.",
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
    args = parser.parse_args()

    settings = ProjectSettings.from_env()
    if args.lora_summary:
        print(json.dumps(inspect_lora_artifact(), ensure_ascii=False, indent=2))
        return

    if args.build_rag_index:
        records = LocalVectorStore(DEFAULT_VECTOR_STORE_PATH).build_from_json(AUDIT_STANDARD_PATH)
        print(
            json.dumps(
                {
                    "vector_store": str(DEFAULT_VECTOR_STORE_PATH),
                    "vector_db": "chroma",
                    "embedding_model": "local_hashing_v1",
                    "records": len(records),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.rag_query:
        print(json.dumps(retrieve_audit_standards([args.rag_query], limit=5), ensure_ascii=False, indent=2))
        return

    if args.demo:
        result = run_demo(args.document)
        print(build_full_report_markdown(result))
        if args.save_report:
            paths = save_reports(result)
            print(f"Saved Markdown report: {paths['markdown']}")
            if paths["docx"]:
                print(f"Saved DOCX report: {paths['docx']}")
        return

    print("FinAudit-Graph Day 1 project scaffold is ready.")
    print(f"Neo4j URI: {settings.neo4j_uri}")
    print("Next step: run `python -m finaudit_graph --demo` to test the workflow.")
