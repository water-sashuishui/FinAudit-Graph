from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..settings import ProjectSettings
from .graph_store import query_graph_related_parties
from .vector_store import DEFAULT_VECTOR_STORE_PATH, LocalVectorStore

# 本模块负责两类“知识检索”：
# 1. 关联方图谱线索：优先 Neo4j，失败时回退到本地 JSON。
# 2. 审计准则检索：优先 Chroma 向量检索，失败时回退关键词匹配。

GRAPH_SAMPLE_PATH = Path("data/graph/related_parties.json")
AUDIT_STANDARD_PATH = Path("data/rag/audit_standards.json")


def load_related_parties(company_name: str) -> list[dict[str, Any]]:
    """从本地 JSON 加载指定企业的关联方 fallback 记录。"""
    if not GRAPH_SAMPLE_PATH.exists():
        return []
    records = json.loads(GRAPH_SAMPLE_PATH.read_text(encoding="utf-8"))
    return [
        {
            "name": item["related_party"],
            "relation": item["relation"],
            "depth": item["depth"],
            "evidence": item["evidence"],
        }
        for item in records
        if item.get("company_name") == company_name
    ]


def query_neo4j_related_parties(
    company_name: str,
    settings: ProjectSettings | None = None,
) -> list[dict[str, Any]]:
    """Neo4j 查询入口；不可用时返回空列表交给上层 fallback。"""
    # 实际查询统一委托给 graph_store，避免知识层和写入层维护两份 Cypher。
    return query_graph_related_parties(company_name, settings=settings)

    settings = settings or ProjectSettings.from_env()
    if not settings.neo4j_uri or settings.neo4j_password == "password":
        return []

    try:
        from neo4j import GraphDatabase
    except ImportError:
        return []

    cypher_query = """
    MATCH (c:Company {name: $company_name})-[r:OWNS|CONTROLS|SUPPLIES*1..3]-(p:Company)
    WHERE any(rel IN r WHERE coalesce(rel.hidden, false) = true OR coalesce(rel.ratio, 0) >= 0.2)
    RETURN p.name AS related_party,
           length(r) AS depth,
           reduce(pathText = '', rel IN r | pathText + type(rel) + ' ') AS relation_path
    LIMIT 20
    """
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        with driver.session() as session:
            records = session.run(cypher_query, company_name=company_name)
            return [
                {
                    "name": record["related_party"],
                    "relation": "Neo4j 关系穿透",
                    "depth": record["depth"],
                    "evidence": record["relation_path"] or "Neo4j query matched a related party path.",
                    "source": "neo4j",
                }
                for record in records
            ]
    except Exception:
        return []
    finally:
        try:
            driver.close()
        except Exception:
            pass


def retrieve_related_parties(company_name: str) -> list[dict[str, Any]]:
    """优先用 Neo4j 检索关联方，失败或无结果时使用本地 JSON 样例。"""
    neo4j_records = query_graph_related_parties(company_name)
    if neo4j_records:
        return neo4j_records
    records = load_related_parties(company_name)
    for item in records:
        item["source"] = "json_fallback"
    return records


def retrieve_audit_standards(
    query_terms: list[str],
    limit: int = 3,
    vector_store_path: Path | str = DEFAULT_VECTOR_STORE_PATH,
) -> list[dict[str, Any]]:
    """优先从本地向量库检索审计准则，再降级为关键词匹配。"""
    if not AUDIT_STANDARD_PATH.exists():
        return []

    query_text = " ".join(query_terms)
    try:
        # ensure_built 让首次查询自动创建索引，演示环境不需要单独预热。
        store = LocalVectorStore(store_path=vector_store_path)
        store.ensure_built(AUDIT_STANDARD_PATH)
        vector_results = store.search(query_text, limit=limit)
        if vector_results:
            return vector_results
    except Exception:
        # 向量库不可用时保持服务可用，下面的关键词检索至少能返回可解释依据。
        pass

    standards = json.loads(AUDIT_STANDARD_PATH.read_text(encoding="utf-8"))
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in standards:
        keywords = item.get("keywords", [])
        content = item.get("content", "")
        score = sum(1 for term in query_terms if term in keywords or term in content)
        if score:
            scored.append(
                (
                    score,
                    {
                        **item,
                        "retrieval_mode": "keyword_fallback",
                        "similarity": 0.0,
                    },
                )
            )

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:limit]]
