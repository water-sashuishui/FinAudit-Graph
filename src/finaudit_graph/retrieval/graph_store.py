from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..settings import ProjectSettings


COMPANY_SUFFIX_PATTERN = r"(?:股份有限公司|集团有限公司|有限责任公司|有限公司)"
COMPANY_NAME_PATTERN = re.compile(rf"[\u4e00-\u9fa5A-Za-z0-9（）()]{{2,30}}?{COMPANY_SUFFIX_PATTERN}")
PERSON_NAME_PATTERN = re.compile(r"[\u4e00-\u9fa5]{1,3}某")


@dataclass(frozen=True)
class GraphNode:
    """A node candidate that can be persisted into Neo4j."""

    label: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphRelationship:
    """A relationship candidate that can be persisted into Neo4j."""

    source_name: str
    target_name: str
    target_label: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphCandidates:
    """Extracted graph write candidates for one parsed audit document."""

    nodes: list[GraphNode]
    relationships: list[GraphRelationship]


def extract_graph_candidates(parsed: dict[str, Any]) -> GraphCandidates:
    """从解析结果中抽取可写入图数据库的确定性节点和关系候选。"""
    company_name = str(parsed.get("company_name") or "").strip()
    if not company_name:
        return GraphCandidates(nodes=[], relationships=[])

    source_file = str(parsed.get("source_file") or "")
    text = _candidate_text(parsed)
    nodes: dict[tuple[str, str], GraphNode] = {
        ("Company", company_name): GraphNode(
            label="Company",
            name=company_name,
            properties={"source_file": source_file} if source_file else {},
        )
    }
    relationships: list[GraphRelationship] = []

    # 图谱抽取保持规则化和可解释：只从原文片段/关键线索里抽候选企业，
    # 再根据附近语境判断关系类型，避免生成无法追溯证据的图边。
    for target in _company_names(text):
        if target == company_name:
            continue
        relation_type = _relationship_type_for_company(text, target)
        if relation_type is None:
            continue
        nodes.setdefault(("Company", target), GraphNode(label="Company", name=target, properties={}))
        relationships.append(
            _relationship(
                company_name,
                target,
                "Company",
                relation_type,
                text,
                source_file,
            )
        )

    for person in _person_names(text):
        # “张某/李某”这类匿名人名只有出现在控制、股东等上下文里才写入图谱。
        if _has_any(text, ["控制人", "实际控制人", "控股", "股东"]):
            nodes.setdefault(("Person", person), GraphNode(label="Person", name=person, properties={}))
            relationships.append(
                _relationship(
                    company_name,
                    person,
                    "Person",
                    "CONTROLLED_BY",
                    text,
                    source_file,
                )
            )

    return GraphCandidates(nodes=list(nodes.values()), relationships=_dedupe_relationships(relationships))


def neo4j_is_configured(settings: ProjectSettings) -> bool:
    """Return whether Neo4j settings look intentionally configured."""
    return bool(settings.neo4j_uri and settings.neo4j_password and settings.neo4j_password != "password")


def graph_status(
    write_status: str,
    *,
    configured: bool,
    available: bool,
    records_written: int = 0,
    error: str = "",
    source: str = "json_fallback",
) -> dict[str, Any]:
    """Build normalized graph ingestion status for workflow/API consumers."""
    return {
        "neo4j_configured": configured,
        "neo4j_available": available,
        "graph_write_status": write_status,
        "graph_write_error": error,
        "graph_records_written": records_written,
        "graph_source": source,
    }


def ingest_parsed_graph(
    parsed: dict[str, Any],
    settings: ProjectSettings | None = None,
    driver_factory: Any | None = None,
) -> dict[str, Any]:
    """Persist extracted graph candidates into Neo4j when configured."""
    current = settings or ProjectSettings.from_env()
    if not neo4j_is_configured(current):
        # 未配置 Neo4j 时跳过写入，但不阻断审计主流程；知识层会继续使用 JSON fallback。
        return graph_status("skipped", configured=False, available=False)

    candidates = extract_graph_candidates(parsed)
    if not candidates.nodes:
        return graph_status("skipped", configured=True, available=False)

    driver = None
    try:
        factory = driver_factory or _default_driver_factory
        driver = factory(current)
        driver.verify_connectivity()
        with driver.session() as session:
            # 约束和 MERGE 都是幂等操作，允许同一材料多次演示运行而不重复造点。
            ensure_graph_constraints(session)
            records_written = write_graph_candidates(session, candidates)
        return graph_status(
            "succeeded",
            configured=True,
            available=True,
            records_written=records_written,
            source="neo4j",
        )
    except Exception as exc:
        return graph_status("failed", configured=True, available=False, error=str(exc))
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:
                pass


def check_neo4j_available(
    settings: ProjectSettings | None = None,
    driver_factory: Any | None = None,
) -> bool:
    """Return true when Neo4j is configured and connectivity succeeds."""
    current = settings or ProjectSettings.from_env()
    if not neo4j_is_configured(current):
        return False

    driver = None
    try:
        factory = driver_factory or _default_driver_factory
        driver = factory(current)
        driver.verify_connectivity()
        return True
    except Exception:
        return False
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:
                pass


def _default_driver_factory(settings: ProjectSettings) -> Any:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError("neo4j driver is not installed") from exc
    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password))


def ensure_graph_constraints(session: Any) -> None:
    """Create idempotent constraints needed by the graph store."""
    session.run(
        """
        CREATE CONSTRAINT company_name_unique IF NOT EXISTS
        FOR (c:Company) REQUIRE c.name IS UNIQUE
        """
    ).consume()
    session.run(
        """
        CREATE CONSTRAINT person_name_unique IF NOT EXISTS
        FOR (p:Person) REQUIRE p.name IS UNIQUE
        """
    ).consume()


def write_graph_candidates(session: Any, candidates: GraphCandidates) -> int:
    """Write candidate nodes and relationships to Neo4j with idempotent MERGE."""
    records_written = 0
    for node in candidates.nodes:
        if node.label == "Person":
            session.run(
                """
                MERGE (node:Person {name: $name})
                SET node += $properties
                """,
                name=node.name,
                properties=node.properties,
            ).consume()
        else:
            session.run(
                """
                MERGE (node:Company {name: $name})
                SET node += $properties
                """,
                name=node.name,
                properties=node.properties,
            ).consume()
        records_written += 1

    for relationship in candidates.relationships:
        _write_relationship(session, relationship)
        records_written += 1
    return records_written


def _write_relationship(session: Any, relationship: GraphRelationship) -> None:
    relation_query = _relationship_query(relationship)
    session.run(
        relation_query,
        source_name=relationship.source_name,
        target_name=relationship.target_name,
        properties=relationship.properties,
    ).consume()


def _relationship_query(relationship: GraphRelationship) -> str:
    target_pattern = "(target:Person {name: $target_name})" if relationship.target_label == "Person" else "(target:Company {name: $target_name})"
    relation_type = relationship.type
    # relation_type 来自内部白名单规则，不接受外部输入，避免拼接 Cypher 类型时引入注入面。
    return f"""
    MERGE (source:Company {{name: $source_name}})
    MERGE {target_pattern}
    MERGE (source)-[rel:{relation_type}]->(target)
    SET rel += $properties
    """


def query_graph_related_parties(
    company_name: str,
    settings: ProjectSettings | None = None,
    driver_factory: Any | None = None,
) -> list[dict[str, Any]]:
    """Query suspicious related-party paths from Neo4j."""
    current = settings or ProjectSettings.from_env()
    if not neo4j_is_configured(current):
        return []

    driver = None
    # 查询 1 到 3 跳关系，并要求路径中至少有隐藏关系、比例阈值或置信度阈值命中，
    # 这样可以过滤掉普通供应链关系，只返回需要审计关注的穿透线索。
    cypher_query = """
    MATCH path = (c:Company {name: $company_name})-[r:CONTROLLED_BY|PURCHASES_FROM|SUPPLIES|HAS_RECEIVABLE_FROM|RELATED_TO*1..3]-(p)
    WHERE p <> c
      AND any(rel IN r WHERE coalesce(rel.hidden, false) = true OR coalesce(rel.ratio, 0) >= 0.2 OR coalesce(rel.confidence, 1.0) >= 0.6)
    RETURN coalesce(p.name, "unknown") AS related_party,
           labels(p) AS labels,
           length(path) AS depth,
           [rel IN r | type(rel) + ":" + coalesce(rel.evidence, "")] AS relation_path
    LIMIT 20
    """
    try:
        factory = driver_factory or _default_driver_factory
        driver = factory(current)
        with driver.session() as session:
            records = session.run(cypher_query, company_name=company_name)
            return [
                {
                    "name": record["related_party"],
                    "relation": "Neo4j 关系穿透",
                    "depth": record["depth"],
                    "evidence": " | ".join(record["relation_path"] or []) or "Neo4j query matched a related party path.",
                    "source": "neo4j",
                }
                for record in records
            ]
    except Exception:
        return []
    finally:
        if driver is not None:
            try:
                driver.close()
            except Exception:
                pass


def _candidate_text(parsed: dict[str, Any]) -> str:
    parts = [str(parsed.get("raw_text_excerpt") or "")]
    parts.extend(str(clue) for clue in parsed.get("key_clues", []) if clue)
    return "\n".join(parts)


def _company_names(text: str) -> list[str]:
    names: list[str] = []
    for match in COMPANY_NAME_PATTERN.finditer(text):
        name = match.group(0).strip("。；，,：:")
        name = re.sub(r"^.*?(?:为|对|与)", "", name)
        names.append(name)
    return list(dict.fromkeys(names))


def _person_names(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(0) for match in PERSON_NAME_PATTERN.finditer(text)))


def _relationship_type_for_company(text: str, target: str) -> str | None:
    window = _evidence_window(text, target)
    if _has_any(window, ["供应商", "采购", "购自"]):
        return "PURCHASES_FROM"
    if _has_any(window, ["应收", "保理", "回款", "客户"]):
        return "HAS_RECEIVABLE_FROM"
    if _has_any(window, ["关联方", "共同控制", "交叉任职", "共同投资"]):
        return "RELATED_TO"
    if _has_any(window, ["控制人", "实际控制人", "控股", "股东"]):
        return "CONTROLLED_BY"
    return None


def _relationship(
    source_name: str,
    target_name: str,
    target_label: str,
    relation_type: str,
    text: str,
    source_file: str,
) -> GraphRelationship:
    # 图边属性保留证据窗口、隐藏标记和置信度，后续报告和答辩可以解释每条边的来源。
    properties: dict[str, Any] = {
        "evidence": _evidence_window(text, target_name),
        "hidden": relation_type in {"RELATED_TO", "CONTROLLED_BY"},
        "confidence": 0.75,
        "created_by": "finaudit_graph_rule_extractor",
    }
    if source_file:
        properties["source_file"] = source_file
    return GraphRelationship(
        source_name=source_name,
        target_name=target_name,
        target_label=target_label,
        type=relation_type,
        properties=properties,
    )


def _evidence_window(text: str, needle: str, width: int = 60) -> str:
    for sentence in re.split(r"[。；;\n\r]+", text):
        if needle in sentence:
            return sentence.strip()
    index = text.find(needle)
    if index < 0:
        return text[: width * 2].strip()
    start = max(0, index - width)
    end = min(len(text), index + len(needle) + width)
    return text[start:end].strip()


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _dedupe_relationships(relationships: list[GraphRelationship]) -> list[GraphRelationship]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[GraphRelationship] = []
    for relationship in relationships:
        key = (relationship.source_name, relationship.target_name, relationship.type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relationship)
    return deduped
