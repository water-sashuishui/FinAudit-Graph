# Neo4j Graph Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract companies and relationship clues from uploaded audit or financial files, persist them to Neo4j when configured, and use Neo4j results before JSON fallback.

**Architecture:** Add a focused `graph_store.py` module under retrieval for deterministic extraction, Neo4j writes, status reporting, and related-party path queries. Keep `knowledge.py` as the public retrieval facade, and integrate ingestion inside `node_graph_searcher` so existing LangGraph topology stays stable.

**Tech Stack:** Python 3.11+, Neo4j Python driver, pytest/unittest, existing FinAudit-Graph workflow modules.

---

## File Structure

- Create `src/finaudit_graph/retrieval/graph_store.py`
  - Defines graph candidate dataclasses, deterministic extraction helpers, Neo4j availability/status helpers, write functions, and query functions.
- Modify `src/finaudit_graph/retrieval/knowledge.py`
  - Delegates Neo4j querying to `graph_store.py` and preserves JSON fallback.
- Modify `src/finaudit_graph/core/nodes.py`
  - Calls graph ingestion before related-party retrieval and writes status into workflow state.
- Modify `src/finaudit_graph/core/state.py`
  - Adds optional graph ingestion status fields.
- Modify `src/finaudit_graph/core/service.py`
  - Exposes Neo4j availability/configuration status.
- Modify `tests/test_workflow.py`
  - Adds tests for extraction, disabled status, mocked writer behavior, fallback, and workflow state.

---

### Task 1: Graph Candidate Extraction

**Files:**
- Create: `src/finaudit_graph/retrieval/graph_store.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing extraction tests**

Add tests that import `extract_graph_candidates` and verify it creates the audited company node plus relationship candidates from representative text.

```python
def test_graph_extraction_builds_company_and_relationship_candidates(self) -> None:
    from finaudit_graph.retrieval.graph_store import extract_graph_candidates

    parsed = {
        "company_name": "华景智能装备股份有限公司",
        "source_file": "sample.txt",
        "raw_text_excerpt": (
            "华景智能装备股份有限公司主要供应商为海河新材料有限公司。"
            "期末对远航商业保理有限公司存在应收款。"
            "张某为疑似实际控制人，且与启明供应链管理有限公司存在关联方关系。"
        ),
    }

    candidates = extract_graph_candidates(parsed)

    assert {"name": "华景智能装备股份有限公司", "label": "Company"} in [
        {"name": node.name, "label": node.label} for node in candidates.nodes
    ]
    relationship_types = {relationship.type for relationship in candidates.relationships}
    assert "PURCHASES_FROM" in relationship_types
    assert "HAS_RECEIVABLE_FROM" in relationship_types
    assert "CONTROLLED_BY" in relationship_types
    assert "RELATED_TO" in relationship_types
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_extraction_builds_company_and_relationship_candidates -q`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` because `graph_store.py` does not exist.

- [ ] **Step 3: Implement minimal extraction code**

Create `graph_store.py` with dataclasses `GraphNode`, `GraphRelationship`, `GraphCandidates`, and `extract_graph_candidates(parsed)`.

Key implementation points:

- Always add `GraphNode(label="Company", name=company_name)`.
- Scan `raw_text_excerpt` plus `key_clues`.
- Extract names matching Chinese company suffixes and simple person names near controller clues.
- Map supplier/purchase clues to `PURCHASES_FROM`.
- Map receivable/factoring/customer clues to `HAS_RECEIVABLE_FROM`.
- Map controller/shareholder clues to `CONTROLLED_BY`.
- Map related-party/common-control clues to `RELATED_TO`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_extraction_builds_company_and_relationship_candidates -q`

Expected: PASS.

---

### Task 2: Neo4j Disabled and Write Status

**Files:**
- Modify: `src/finaudit_graph/retrieval/graph_store.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing disabled-status test**

```python
def test_graph_ingestion_skips_when_neo4j_uses_default_password(self) -> None:
    from finaudit_graph.retrieval.graph_store import ingest_parsed_graph
    from finaudit_graph.settings import ProjectSettings

    parsed = {"company_name": "华景智能装备股份有限公司", "source_file": "sample.txt"}
    settings = ProjectSettings(neo4j_uri="bolt://localhost:7687", neo4j_username="neo4j", neo4j_password="password")

    status = ingest_parsed_graph(parsed, settings=settings)

    self.assertEqual("skipped", status["graph_write_status"])
    self.assertFalse(status["neo4j_available"])
    self.assertEqual(0, status["graph_records_written"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_ingestion_skips_when_neo4j_uses_default_password -q`

Expected: FAIL because `ingest_parsed_graph` is not implemented.

- [ ] **Step 3: Implement skipped status**

Add:

- `neo4j_is_configured(settings) -> bool`
- `empty_graph_status(status, error="") -> dict[str, Any]`
- `ingest_parsed_graph(parsed, settings=None) -> dict[str, Any]`

When Neo4j is not configured or password is `password`, return:

```python
{
    "neo4j_configured": False,
    "neo4j_available": False,
    "graph_write_status": "skipped",
    "graph_write_error": "",
    "graph_records_written": 0,
    "graph_source": "json_fallback",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_ingestion_skips_when_neo4j_uses_default_password -q`

Expected: PASS.

---

### Task 3: Neo4j Writer With Mocked Driver

**Files:**
- Modify: `src/finaudit_graph/retrieval/graph_store.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing mocked writer test**

Use a fake session that records Cypher calls. Pass a `driver_factory` into `ingest_parsed_graph` to avoid a live Neo4j requirement.

```python
def test_graph_ingestion_writes_candidates_with_driver_factory(self) -> None:
    from finaudit_graph.retrieval.graph_store import ingest_parsed_graph
    from finaudit_graph.settings import ProjectSettings

    class FakeResult:
        def consume(self):
            return None

    class FakeSession:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **params):
            self.calls.append((query, params))
            return FakeResult()

    class FakeDriver:
        def __init__(self):
            self.session_obj = FakeSession()
            self.closed = False

        def session(self):
            return self.session_obj

        def verify_connectivity(self):
            return None

        def close(self):
            self.closed = True

    fake_driver = FakeDriver()

    parsed = {
        "company_name": "华景智能装备股份有限公司",
        "source_file": "sample.txt",
        "raw_text_excerpt": "华景智能装备股份有限公司主要供应商为海河新材料有限公司。",
    }
    settings = ProjectSettings(neo4j_uri="bolt://localhost:7687", neo4j_username="neo4j", neo4j_password="secret")

    status = ingest_parsed_graph(parsed, settings=settings, driver_factory=lambda _: fake_driver)

    self.assertEqual("succeeded", status["graph_write_status"])
    self.assertTrue(status["neo4j_available"])
    self.assertGreaterEqual(status["graph_records_written"], 2)
    self.assertTrue(fake_driver.closed)
    self.assertTrue(any("MERGE (source:Company" in query for query, _ in fake_driver.session_obj.calls))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_ingestion_writes_candidates_with_driver_factory -q`

Expected: FAIL because writer behavior is not implemented.

- [ ] **Step 3: Implement writer**

Implement:

- `_default_driver_factory(settings)`
- `ensure_graph_constraints(session)`
- `write_graph_candidates(session, candidates) -> int`

Use `MERGE` for nodes and relationships. Use separate Cypher branches for `Company` and `Person` target labels to avoid dynamic labels in Cypher.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_ingestion_writes_candidates_with_driver_factory -q`

Expected: PASS.

---

### Task 4: Related-Party Query Delegation and Fallback

**Files:**
- Modify: `src/finaudit_graph/retrieval/graph_store.py`
- Modify: `src/finaudit_graph/retrieval/knowledge.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing query tests**

Add one test where mocked `query_graph_related_parties` returns a record and `retrieve_related_parties` uses it. Add one fallback test where Neo4j returns an empty list.

```python
def test_related_party_retrieval_uses_neo4j_before_json_fallback(self) -> None:
    from unittest.mock import patch
    from finaudit_graph.retrieval.knowledge import retrieve_related_parties

    with patch(
        "finaudit_graph.retrieval.knowledge.query_graph_related_parties",
        return_value=[{"name": "海河新材料有限公司", "relation": "Neo4j 关系穿透", "depth": 1, "evidence": "PURCHASES_FROM", "source": "neo4j"}],
    ):
        records = retrieve_related_parties("华景智能装备股份有限公司")

    self.assertEqual("neo4j", records[0]["source"])
    self.assertEqual("海河新材料有限公司", records[0]["name"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_related_party_retrieval_uses_neo4j_before_json_fallback -q`

Expected: FAIL because `knowledge.py` does not import the new query facade yet.

- [ ] **Step 3: Implement query facade and delegate from knowledge.py**

Move Neo4j query implementation to `query_graph_related_parties(company_name, settings=None, driver_factory=None)`.

Update `knowledge.py`:

```python
from .graph_store import query_graph_related_parties

def query_neo4j_related_parties(company_name, settings=None):
    return query_graph_related_parties(company_name, settings=settings)
```

Keep `retrieve_related_parties()` behavior unchanged.

- [ ] **Step 4: Run query tests**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_related_party_retrieval_uses_neo4j_before_json_fallback -q`

Expected: PASS.

---

### Task 5: Workflow Integration

**Files:**
- Modify: `src/finaudit_graph/core/nodes.py`
- Modify: `src/finaudit_graph/core/state.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing workflow status test**

```python
def test_graph_searcher_adds_graph_ingestion_status(self) -> None:
    from unittest.mock import patch
    from finaudit_graph.core.nodes import node_graph_searcher

    state = {
        "raw_document_path": "data/demo_inputs/test_audit.txt",
        "parsed_financial_data": {
            "company_name": "华景智能装备股份有限公司",
            "source_file": "test_audit.txt",
            "raw_text_excerpt": "华景智能装备股份有限公司主要供应商为海河新材料有限公司。",
        },
    }

    with patch(
        "finaudit_graph.core.nodes.ingest_parsed_graph",
        return_value={
            "neo4j_configured": True,
            "neo4j_available": True,
            "graph_write_status": "succeeded",
            "graph_write_error": "",
            "graph_records_written": 2,
            "graph_source": "neo4j",
        },
    ):
        result = node_graph_searcher(state)

    self.assertEqual("succeeded", result["graph_write_status"])
    self.assertEqual(2, result["graph_records_written"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_searcher_adds_graph_ingestion_status -q`

Expected: FAIL because `node_graph_searcher` does not call ingestion yet.

- [ ] **Step 3: Integrate ingestion**

Import `ingest_parsed_graph` in `nodes.py`.

Inside `node_graph_searcher`, after `company_name` is established and before `retrieve_related_parties(company_name)`, call:

```python
graph_status = ingest_parsed_graph({**parsed, "company_name": company_name})
```

Merge `graph_status` into returned state.

Update `AuditSystemState` with optional keys:

- `neo4j_configured: bool`
- `neo4j_available: bool`
- `graph_write_status: str`
- `graph_write_error: str`
- `graph_records_written: int`
- `graph_source: str`

- [ ] **Step 4: Run workflow status test**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_graph_searcher_adds_graph_ingestion_status -q`

Expected: PASS.

---

### Task 6: Config Status and Verification

**Files:**
- Modify: `src/finaudit_graph/core/service.py`
- Test: `tests/test_workflow.py`

- [ ] **Step 1: Write failing config status test**

```python
def test_config_status_reports_neo4j_availability_flag(self) -> None:
    from unittest.mock import patch
    from finaudit_graph.core.service import build_config_status
    from finaudit_graph.settings import ProjectSettings

    settings = ProjectSettings(neo4j_uri="bolt://localhost:7687", neo4j_username="neo4j", neo4j_password="secret")

    with patch("finaudit_graph.core.service.check_neo4j_available", return_value=True):
        status = build_config_status(settings)

    self.assertTrue(status["neo4j_configured"])
    self.assertTrue(status["neo4j_available"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_config_status_reports_neo4j_availability_flag -q`

Expected: FAIL because service does not expose `neo4j_available`.

- [ ] **Step 3: Implement status flag**

Import `check_neo4j_available` from `graph_store.py`.

Add `neo4j_available` to `build_config_status()`. It should return false when not configured and should catch exceptions.

- [ ] **Step 4: Run targeted tests**

Run:

```powershell
python -m pytest tests/test_workflow.py::FinAuditGraphTests::test_config_status_reports_neo4j_availability_flag -q
python -m pytest tests/test_workflow.py -q
python -m pytest tests/test_api.py -q
```

Expected: PASS.

---

## Final Verification

- [ ] Run `python -m pytest tests/test_workflow.py tests/test_api.py -q`
- [ ] Run `python -m finaudit_graph --demo`
- [ ] Confirm demo state/report still runs when Neo4j is unavailable.
- [ ] Inspect `git diff` and confirm only planned files changed.
- [ ] Summarize behavior, tests, and any manual Neo4j steps in the final response.

