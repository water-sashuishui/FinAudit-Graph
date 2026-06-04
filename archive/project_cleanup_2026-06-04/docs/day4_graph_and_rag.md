# Day 4 Neo4j 与 RAG 增强说明

## 目标

Day 4 的目标是让审计智能体不只依赖模型常识，而是能展示两类外部增强：

- Neo4j：用于企业股权、控制关系、供应商和资金往来的关联方穿透。
- RAG：用于检索审计准则、内控关注点和风险判断依据。

## Neo4j 样本图谱

- 样本数据：`data/graph/related_parties.json`
- 初始化脚本：`data/graph/init_neo4j.cypher`

本地 Neo4j 可用时，在 Neo4j Browser 或 Cypher Shell 中执行初始化脚本。当前代码中的 `Graph_Searcher` 节点已保留标准 Cypher 查询模板，并先使用 JSON fallback 保证演示稳定。

## RAG 准则库

- 准则片段：`data/rag/audit_standards.json`
- 本地向量库：`data/rag/vector_store.json`
- 检索模块：`src/finaudit_graph/knowledge.py`
- 向量库模块：`src/finaudit_graph/vector_store.py`

当前已经实现本地持久化向量数据库。系统会将审计准则的标题、关键词和正文编码为固定维度向量，并保存到 `data/rag/vector_store.json`。`Compliance_Checker` 节点检索准则时会优先使用向量相似度；如果向量库缺失或损坏，会自动重建；如果检索异常，则回退关键词检索，保证演示稳定。

构建或重建向量库：

```powershell
python -m finaudit_graph --build-rag-index
```

查询向量库：

```powershell
python -m finaudit_graph --rag-query "收入增长和应收账款异常，需要关注截止性"
```

当前 embedding 模式为 `local_hashing_v1`，不依赖外部 API 和模型下载。后续生产化可以替换为 Chroma、FAISS、sentence-transformers 或云端 embedding 服务，接口保持为输入查询词、输出准则片段。

## 验收方式

运行：

```powershell
python -m finaudit_graph --demo
```

输出报告应包含：

- 至少 2 个潜在关联方。
- 收入确认、关联方披露、内控、成本结转等审计依据。
- 风险等级、判断依据和整改建议。
- RAG 检索结果带有 `retrieval_mode: vector` 和相似度分数。
