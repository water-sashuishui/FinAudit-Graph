from __future__ import annotations

import unittest
import subprocess
import sys
import tempfile
import os
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["NEO4J_PASSWORD"] = "password"

from finaudit_graph.llm import DeepSeekClient, normalize_chat_completions_url
from finaudit_graph.settings import ProjectSettings
from finaudit_graph.automation import build_n8n_payload, send_to_n8n
from finaudit_graph.lora import inspect_lora_artifact
from finaudit_graph.reporting import build_full_report_markdown
from finaudit_graph.workflow import run_demo
from finaudit_graph.knowledge import retrieve_audit_standards


class FinAuditWorkflowTest(unittest.TestCase):
    def test_demo_workflow_generates_audit_summary(self) -> None:
        state = run_demo()

        self.assertIn("parsed_financial_data", state)
        self.assertGreaterEqual(len(state["discovered_related_parties"]), 2)
        self.assertGreaterEqual(len(state["audit_risks_found"]), 3)
        self.assertIn("智能审计综述", state["final_audit_summary"])

    def test_n8n_payload_dry_run(self) -> None:
        state = run_demo()
        payload = build_n8n_payload(state)
        result = send_to_n8n(payload)

        self.assertEqual(payload["company_name"], "华辰智能装备股份有限公司")
        self.assertEqual(payload["risk_count"], len(state["audit_risks_found"]))
        self.assertFalse(result["sent"])
        self.assertEqual(result["mode"], "dry_run")

    def test_lora_artifact_summary_reads_adapter_outputs(self) -> None:
        summary = inspect_lora_artifact(Path("model_artifacts/lora_adapter"))

        self.assertEqual(summary["artifact_type"], "LoRA adapter")
        self.assertEqual(summary["base_model"], "Qwen2.5-1.5B-Instruct")
        self.assertEqual(summary["train_samples"], 80)
        self.assertIn("adapter_model.safetensors", summary["files"])

    def test_full_report_markdown_contains_mvp_sections(self) -> None:
        state = run_demo()
        report = build_full_report_markdown(state)

        self.assertIn("企业合规风控审计报告", report)
        self.assertIn("一、执行摘要", report)
        self.assertIn("五、整改建议与复核计划", report)
        self.assertIn("七、自动化记录 Payload 摘要", report)

    def test_cli_lora_summary_prints_adapter_status(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "finaudit_graph", "--lora-summary"],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("LoRA adapter", result.stdout)
        self.assertIn("Qwen2.5-1.5B-Instruct", result.stdout)

    def test_streamlit_frontend_hides_lora_technical_artifacts(self) -> None:
        app_source = Path("apps/streamlit_app.py").read_text(encoding="utf-8")

        self.assertNotIn("inspect_lora_artifact", app_source)
        self.assertNotIn("LoRA 微调成果", app_source)

    def test_project_paths_use_ascii_names_outside_environment_dirs(self) -> None:
        ignored_parts = {".git", ".venv", "__pycache__", ".pytest_cache"}
        non_ascii_paths = []
        for path in Path(".").rglob("*"):
            if any(part in ignored_parts for part in path.parts):
                continue
            if any(ord(character) > 127 for character in path.name):
                non_ascii_paths.append(str(path))

        self.assertEqual([], non_ascii_paths)

    def test_report_output_filenames_are_ascii(self) -> None:
        from finaudit_graph.reporting import save_reports

        state = run_demo()
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = save_reports(state, output_dir=tmp_dir)

            for path_text in paths.values():
                if path_text is None:
                    continue
                self.assertTrue(Path(path_text).exists())
                self.assertTrue(path_text.isascii(), path_text)

    def test_save_reports_keeps_markdown_when_docx_file_is_locked(self) -> None:
        from finaudit_graph.reporting import save_reports

        state = run_demo()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("docx.document.Document.save", side_effect=PermissionError("locked")):
                paths = save_reports(state, output_dir=tmp_dir)
            self.assertTrue(Path(paths["markdown"]).exists())
            self.assertIsNone(paths["docx"])

    def test_deepseek_url_normalization_matches_openai_compatible_api(self) -> None:
        self.assertEqual(
            "https://api.deepseek.com/v1/chat/completions",
            normalize_chat_completions_url("https://api.deepseek.com"),
        )
        self.assertEqual(
            "https://api.deepseek.com/v1/chat/completions",
            normalize_chat_completions_url("https://api.deepseek.com/v1"),
        )

    def test_deepseek_client_uses_bearer_key_and_chat_messages(self) -> None:
        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return b'{"choices":[{"message":{"content":"{\\"risks\\":[]}"}}]}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["data"] = request.data.decode("utf-8")
            captured["timeout"] = timeout
            return FakeResponse()

        client = DeepSeekClient(
            ProjectSettings(
                deepseek_api_key="sk-test",
                deepseek_base_url="https://api.deepseek.com",
                audit_llm_model="deepseek-chat",
            )
        )
        with patch("urllib.request.urlopen", fake_urlopen):
            content = client.chat(
                [
                    {"role": "system", "content": "You are an auditor."},
                    {"role": "user", "content": "Analyze risks."},
                ]
            )

        self.assertEqual('{"risks":[]}', content)
        self.assertEqual("https://api.deepseek.com/v1/chat/completions", captured["url"])
        self.assertEqual("Bearer sk-test", captured["headers"]["Authorization"])
        self.assertIn('"model": "deepseek-chat"', captured["data"])
        self.assertIn('"role": "system"', captured["data"])

    def test_langchain_deepseek_agent_parses_structured_risks(self) -> None:
        from langchain_core.messages import AIMessage
        from finaudit_graph.audit_agent import run_langchain_audit_agent

        class FakeAgent:
            def invoke(self, payload):
                self.payload = payload
                return {
                    "messages": [
                        AIMessage(
                            content=(
                                '{"risks":[{"risk_type":"Agent收入异常","severity":"高",'
                                '"evidence":"Agent 调用了指标与RAG工具。",'
                                '"audit_basis":"收入确认准则片段",'
                                '"recommendation":"复核合同、验收和回款。"}]}'
                            )
                        )
                    ]
                }

        risks = run_langchain_audit_agent(
            parsed={"company_name": "测试科技有限公司", "revenue_growth_rate": 35.5},
            related_parties=[],
            standards=[],
            agent_executor=FakeAgent(),
        )

        self.assertIsNotNone(risks)
        self.assertEqual("Agent收入异常", risks[0]["risk_type"])
        self.assertEqual("高", risks[0]["severity"])

    def test_compliance_checker_prefers_langchain_agent_when_available(self) -> None:
        from finaudit_graph.nodes import node_compliance_checker

        state = {
            "parsed_financial_data": {
                "company_name": "测试科技有限公司",
                "revenue_growth_rate": 35.5,
                "operating_cashflow_growth_rate": -8.2,
                "gross_margin_rate": 48.0,
                "accounts_receivable_growth_rate": 44.0,
            },
            "discovered_related_parties": [],
        }
        with patch(
            "finaudit_graph.nodes.run_langchain_audit_agent",
            return_value=[
                {
                    "risk_type": "Agent审计风险",
                    "severity": "高",
                    "evidence": "LangChain Agent 工具调用结果。",
                    "audit_basis": "RAG 准则",
                    "recommendation": "执行进一步审计程序。",
                }
            ],
        ):
            result = node_compliance_checker(state)

        self.assertEqual("langchain_deepseek_agent", result["llm_provider"])
        self.assertEqual("Agent审计风险", result["audit_risks_found"][0]["risk_type"])

    def test_txt_document_parser_uses_uploaded_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            document_path = Path(tmp_dir) / "sample_audit.txt"
            document_path.write_text(
                "被审计企业：测试科技有限公司\n"
                "报告年度：2024\n"
                "收入增长率：35.5%\n"
                "经营现金流增长率：-8.2%\n"
                "毛利率：58.1%\n"
                "应收账款增长率：44.0%\n",
                encoding="utf-8",
            )

            state = run_demo(str(document_path))

        parsed = state["parsed_financial_data"]
        self.assertEqual("测试科技有限公司", parsed["company_name"])
        self.assertEqual(2024, parsed["reporting_year"])
        self.assertEqual(35.5, parsed["revenue_growth_rate"])

    def test_xlsx_document_parser_semantically_aligns_financial_fields(self) -> None:
        from finaudit_graph.parsing import parse_financial_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            document_path = Path(tmp_dir) / "financial_data.xlsx"
            _write_minimal_xlsx(
                document_path,
                [
                    ["公司名称", "星河智能制造有限公司"],
                    ["会计年度", "2024"],
                    ["指标", "本期数"],
                    ["主营业务收入增长", "36.8%"],
                    ["经营活动现金流同比", "-9.4%"],
                    ["综合毛利率", "57.2%"],
                    ["应收账款同比", "41.6%"],
                ],
            )

            parsed = parse_financial_document(document_path)

        self.assertEqual("星河智能制造有限公司", parsed["company_name"])
        self.assertEqual(2024, parsed["reporting_year"])
        self.assertEqual(36.8, parsed["revenue_growth_rate"])
        self.assertEqual(-9.4, parsed["operating_cashflow_growth_rate"])
        self.assertEqual(57.2, parsed["gross_margin_rate"])
        self.assertEqual(41.6, parsed["accounts_receivable_growth_rate"])
        self.assertEqual("semantic_table_alignment", parsed["extraction_method"])
        self.assertIn("revenue_growth_rate", parsed["extraction_evidence"])

    def test_csv_document_parser_aligns_values_from_table_headers(self) -> None:
        from finaudit_graph.parsing import parse_financial_document

        with tempfile.TemporaryDirectory() as tmp_dir:
            document_path = Path(tmp_dir) / "financial_data.csv"
            document_path.write_text(
                "被审计单位,报告年度,营业收入同比,经营现金流同比,毛利率,应收款增长\n"
                "远景精密设备有限公司,2023,28.5%,-6.7%,52.4%,33.1%\n",
                encoding="utf-8",
            )

            parsed = parse_financial_document(document_path)

        self.assertEqual("远景精密设备有限公司", parsed["company_name"])
        self.assertEqual(2023, parsed["reporting_year"])
        self.assertEqual(28.5, parsed["revenue_growth_rate"])
        self.assertEqual(-6.7, parsed["operating_cashflow_growth_rate"])
        self.assertEqual(52.4, parsed["gross_margin_rate"])
        self.assertEqual(33.1, parsed["accounts_receivable_growth_rate"])

    def test_no_related_party_risk_when_graph_has_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            document_path = Path(tmp_dir) / "sample_audit.txt"
            document_path.write_text(
                "被审计企业：测试科技有限公司\n"
                "报告年度：2024\n"
                "收入增长率：35.5%\n"
                "经营现金流增长率：-8.2%\n"
                "毛利率：58.1%\n"
                "应收账款增长率：44.0%\n",
                encoding="utf-8",
            )

            state = run_demo(str(document_path))

        risk_types = {risk["risk_type"] for risk in state["audit_risks_found"]}
        self.assertNotIn("关联方利益输送", risk_types)

    def test_vector_store_builds_persistent_audit_standard_index(self) -> None:
        from finaudit_graph.vector_store import LocalVectorStore

        with tempfile.TemporaryDirectory() as tmp_dir:
            store_path = Path(tmp_dir) / "chroma_db"
            store = LocalVectorStore(store_path=store_path)
            records = store.build_from_json(Path("data/rag/audit_standards.json"))

            self.assertTrue((store_path / "manifest.json").exists())
            self.assertEqual(4, len(records))
            self.assertTrue(all(record["vector"] for record in records))
            self.assertEqual("local_hashing_v1", records[0]["embedding_model"])

    def test_audit_standard_retrieval_uses_vector_store_before_keyword_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store_path = Path(tmp_dir) / "chroma_db"

            results = retrieve_audit_standards(
                ["销售回款与应收账款异常增长，需要关注收入截止性"],
                limit=2,
                vector_store_path=store_path,
            )

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual("revenue-recognition", results[0]["id"])
        self.assertEqual("chroma_vector", results[0]["retrieval_mode"])
        self.assertGreater(results[0]["similarity"], 0)

def _write_minimal_xlsx(path: Path, rows: list[list[str]]) -> None:
    def cell_name(row_index: int, col_index: int) -> str:
        return f"{chr(ord('A') + col_index)}{row_index + 1}"

    sheet_rows = []
    for row_index, row in enumerate(rows):
        cells = []
        for col_index, value in enumerate(row):
            escaped = (
                str(value)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            cells.append(
                f'<c r="{cell_name(row_index, col_index)}" t="inlineStr">'
                f"<is><t>{escaped}</t></is></c>"
            )
        sheet_rows.append(f'<row r="{row_index + 1}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="审计数据" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


if __name__ == "__main__":
    unittest.main()
