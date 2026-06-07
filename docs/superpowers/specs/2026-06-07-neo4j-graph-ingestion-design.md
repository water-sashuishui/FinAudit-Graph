# Neo4j Graph Ingestion Design

Date: 2026-06-07

## Goal

FinAudit-Graph should extract enterprise and relationship clues from uploaded audit or financial files, persist them into Neo4j, and use the persisted graph during related-party risk discovery.

The workflow must remain runnable when Neo4j is unavailable. Neo4j should improve graph evidence and traceability, not become a hard dependency for the whole audit demo.

## Current Context

The project already has partial Neo4j support:

- `ProjectSettings` loads `NEO4J_URI`, `NEO4J_USERNAME`, and `NEO4J_PASSWORD`.
- `requirements.txt` includes the `neo4j` Python driver.
- `retrieve_related_parties()` tries Neo4j first and falls back to `data/graph/related_parties.json`.
- `data/graph/init_neo4j.cypher` contains sample graph setup data.

The main gap is that the current Neo4j query and sample graph schema do not match. The query uses `OWNS|CONTROLS|SUPPLIES`, while the sample script uses `CONTROLLED_BY`, `HAS_RECEIVABLE_FROM`, `PURCHASES_FROM`, and `RELATED_TO`. This means a configured Neo4j instance can still return no matches.

The second gap is that uploaded documents are parsed for audit facts, but their graph-worthy entities and relationships are not written back to Neo4j.

## Recommended Approach

Add a small Neo4j graph persistence layer while keeping the existing workflow shape.

The audit flow becomes:

1. Parse the uploaded document into structured financial facts.
2. Extract graph candidates from parsed facts and source text.
3. Write companies, people, and relationships to Neo4j when configured.
4. Query Neo4j for suspicious related-party paths.
5. Fall back to local JSON graph records when Neo4j is unavailable or empty.
6. Continue risk classification and report generation.

This approach keeps changes localized and preserves demo reliability.

## New Module

Add `src/finaudit_graph/retrieval/graph_store.py`.

Responsibilities:

- Create and close Neo4j drivers.
- Check Neo4j availability.
- Ensure graph constraints.
- Convert extracted candidates into Neo4j `MERGE` operations.
- Query related-party paths using the actual relationship types used by the project.
- Return structured status metadata for API/UI display.

`knowledge.py` remains the high-level retrieval entry point. It should delegate Neo4j-specific work to `graph_store.py`.

## Data Model

Nodes:

- `(:Company {name})`
- `(:Person {name})`

Company properties may include:

- `industry`
- `listed`
- `source_file`
- `last_seen_at`

Relationship types:

- `CONTROLLED_BY`
- `PURCHASES_FROM`
- `SUPPLIES`
- `HAS_RECEIVABLE_FROM`
- `RELATED_TO`

Relationship properties:

- `evidence`
- `source_file`
- `amount`
- `ratio`
- `hidden`
- `confidence`
- `created_by`
- `last_seen_at`

The first implementation should use deterministic rule extraction. LLM-based relationship extraction can be added later, but it should not be required for the base Neo4j feature.

## Extraction Rules

The extractor should always create a `Company` node for `parsed_financial_data["company_name"]` when present.

It should then scan available source text and parsed fields for relationship clues:

- Supplier or purchase clues produce `PURCHASES_FROM` or `SUPPLIES`.
- Receivable, factoring, repayment, or customer clues produce `HAS_RECEIVABLE_FROM`.
- Controller, shareholder, actual controller, holding, or ratio clues produce `CONTROLLED_BY`.
- Related-party, cross-appointment, common investment, or hidden connection clues produce `RELATED_TO`.

When confidence is uncertain, write the relation with `confidence < 1.0` and keep the original evidence text.

## Workflow Integration

Update `node_graph_searcher` or add a small graph ingestion node after parsing.

Recommended minimal integration:

- `node_data_parser` continues parsing only.
- `node_graph_searcher` calls graph ingestion before querying related parties.
- The node writes graph ingestion status into workflow state, for example:
  - `graph_write_status`
  - `graph_write_error`
  - `graph_records_written`
  - `graph_source`

This avoids widening the LangGraph topology while still persisting uploaded-document graph clues before retrieval.

## Query Design

Update the Neo4j related-party query to include the relationship types actually written by the project:

```cypher
MATCH path = (c:Company {name: $company_name})-[r:CONTROLLED_BY|PURCHASES_FROM|SUPPLIES|HAS_RECEIVABLE_FROM|RELATED_TO*1..3]-(p)
WHERE p <> c
  AND any(rel IN r WHERE coalesce(rel.hidden, false) = true OR coalesce(rel.ratio, 0) >= 0.2 OR coalesce(rel.confidence, 1.0) >= 0.6)
RETURN coalesce(p.name, "unknown") AS related_party,
       labels(p) AS labels,
       length(path) AS depth,
       [rel IN r | type(rel) + ":" + coalesce(rel.evidence, "")] AS relation_path
LIMIT 20
```

The returned records should keep the existing shape expected by downstream code:

- `name`
- `relation`
- `depth`
- `evidence`
- `source`

## Error Handling

Neo4j failures must not stop the audit workflow.

Expected behavior:

- Missing driver: skip Neo4j and use fallback.
- Default password or empty URI: skip Neo4j and use fallback.
- Connection failure: record status as failed and use fallback.
- Write failure: continue query if possible, otherwise fallback.
- Query failure: use fallback.

Errors should not be swallowed completely. Store a short diagnostic string in workflow state or status output so the UI/API can explain whether Neo4j was used.

## API/UI Status

Extend config/status or audit result payloads with graph information:

- `neo4j_configured`
- `neo4j_available`
- `graph_write_status`
- `graph_records_written`
- `graph_source`

This gives a clear demo signal that the uploaded document contributed to the graph.

## Testing

Add focused tests without requiring a live Neo4j instance:

- Graph extraction returns candidates from parsed data and representative text.
- Neo4j disabled or default password returns a skipped status.
- Graph writer sends expected Cypher parameters to a mocked session.
- Related-party retrieval uses Neo4j results before JSON fallback.
- Related-party retrieval falls back when Neo4j returns empty results or raises.
- Workflow state includes graph ingestion status after a demo run.

A live Neo4j smoke test can be documented as an optional manual step rather than required in CI.

## Out Of Scope

The first implementation will not:

- Build a full named-entity recognition system.
- Require DeepSeek or another LLM to extract graph relations.
- Delete or overwrite previously ingested graph data.
- Make Neo4j mandatory for running the audit workflow.
- Replace the existing local JSON fallback.

