from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from finaudit_graph.api import app


class FinAuditApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    def test_config_status_endpoint(self) -> None:
        response = self.client.get("/api/config/status")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertIn("deepseek_configured", payload)
        self.assertIn("n8n_configured", payload)

    def test_rag_query_endpoint(self) -> None:
        response = self.client.post("/api/rag/query", json={"query": "收入确认", "limit": 2})

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("收入确认", payload["query"])
        self.assertLessEqual(len(payload["results"]), 2)

    def test_audit_run_with_document_path(self) -> None:
        response = self.client.post(
            "/api/audit/run",
            data={"document_path": "showcase/demo_inputs/test_audit.txt", "save_report": "false"},
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("completed", payload["status"])
        self.assertIn("parsed_financial_data", payload)
        self.assertIn("final_report_markdown", payload)
        self.assertIn("n8n_result", payload)
        self.assertIn("negotiation_trace", payload)
        self.assertIn("llm_provider", payload)

    def test_audit_run_with_upload(self) -> None:
        file_bytes = Path("showcase/demo_inputs/test_audit.txt").read_bytes()
        response = self.client.post(
            "/api/audit/run",
            files={"file": ("test_audit.txt", file_bytes, "text/plain")},
        )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("completed", payload["status"])
        self.assertTrue(payload["document_path"].endswith(".txt"))

    def test_audit_run_rejects_missing_input(self) -> None:
        response = self.client.post("/api/audit/run")

        self.assertEqual(400, response.status_code)
        self.assertIn("Provide either an uploaded file or a document_path", response.json()["detail"])

    def test_audit_run_rejects_invalid_path(self) -> None:
        response = self.client.post("/api/audit/run", data={"document_path": "showcase/demo_inputs/missing.txt"})

        self.assertEqual(404, response.status_code)


if __name__ == "__main__":
    unittest.main()
