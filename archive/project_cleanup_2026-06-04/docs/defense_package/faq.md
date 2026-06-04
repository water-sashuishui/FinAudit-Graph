# FinAudit-Graph 答辩 FAQ

## 1. 为什么使用 LangGraph？

审计流程天然是多步骤状态流转：先解析材料，再查关联方，再做合规判断，最后生成报告。LangGraph 可以把这些步骤显式编排成节点和边，便于调试、解释和扩展。相比普通链式调用，它更适合展示“每个智能体负责什么、输入输出是什么、状态如何传递”。

## 1.1 LangChain Agent 在哪里使用？

LangChain Agent 被放在 `Compliance_Checker` 合规审查节点中。配置 DeepSeek 后，系统会创建 LangChain 1.x Agent，以 DeepSeek 作为基座模型，并让 Agent 调用财务指标分析工具、RAG 检索工具和关联方线索工具来完成风险判断。Agent 失败时会自动回退 DeepSeek 直接调用或本地规则版，保证演示稳定。

## 2. 为什么使用 LoRA 微调？

通用大模型虽然能理解财务文本，但对审计风险标签、风险等级和专业表达不一定稳定。LoRA 是轻量化微调方式，适合在有限算力和时间下证明“领域适配”流程。本项目已经用 80 条 Label Studio 标注数据训练出 LoRA adapter，并保留训练日志和 loss 曲线作为过程证据。

## 3. LoRA adapter 是完整模型吗？

不是。`adapter_model.safetensors` 和 `adapter_config.json` 是适配器权重，需要配合基座模型 `Qwen2.5-1.5B-Instruct` 加载。答辩中可以强调它证明了模型层训练闭环，但当前 MVP 主链路仍优先保证稳定演示。

## 4. Neo4j 的作用是什么？

Neo4j 用于表达企业、股东、供应商、资金往来和控制关系。审计中的关联方穿透非常适合图数据库建模。当前 MVP 如果 Neo4j 没启动，会使用 `data/graph/related_parties.json` 作为 fallback；如果配置了真实 Neo4j，则可以替换为实时 Cypher 查询。

## 5. RAG 的作用是什么？

RAG 用于把审计准则、法规依据和内控关注点带入风险判断，避免模型只凭常识输出。当前 MVP 已经把本地 JSON 准则库构建为 `data/rag/vector_store.json` 持久化向量库，检索时优先按向量相似度召回准则片段；如果向量库异常，则回退关键词检索。后续可以升级为 Chroma 或 FAISS，并接入更强 embedding 模型。

## 6. DeepSeek 在项目里怎么使用？

项目读取 `.env` 中的：

```text
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
AUDIT_LLM_MODEL
```

并按 OpenAI-compatible chat completions 格式调用：

```text
Authorization: Bearer <DEEPSEEK_API_KEY>
```

如果 API 不可用、超时或返回格式不符合要求，系统会自动回退本地规则版风险判断，保证演示不中断。

## 7. 为什么前端不展示 LoRA 微调成果？

前端面向审计用户，用户关心上传材料、查看风险和下载报告。LoRA 属于技术实现和答辩证明材料，不适合放在业务用户界面中。因此项目保留 CLI 和文档展示 LoRA 成果，而前端只展示业务流程。

## 8. N8N 和飞书目前做到什么程度？

当前 MVP 已经能生成 N8N Webhook payload；未配置真实 webhook 时会进入 dry-run。飞书真实写入需要配置 app id、app secret、base app token、table id，并确保应用权限已开通。答辩演示阶段优先使用 dry-run payload 保证稳定。

## 9. 当前系统的局限是什么？

- PDF/财报解析仍是基础文本抽取；Excel/CSV 已支持常见字段语义对齐，但复杂合并单元格、多期间表和扫描件仍需要进一步增强 OCR 与表格结构化能力。
- RAG 目前是本地轻量向量库，语义能力弱于 sentence-transformers/Chroma/FAISS 等生产级方案。
- Neo4j 和飞书真实服务依赖外部配置，当前以 fallback 保证演示稳定。
- LoRA adapter 已训练完成，但本地推理对比脚本仍可进一步补充。

## 10. 项目的创新点是什么？

项目把财务审计拆解为多智能体流程，并把 LoRA 微调、图谱穿透、RAG 准则依据、DeepSeek API 和自动化 payload 串成一个可运行 MVP。它的重点不是单点模型调用，而是审计业务流程的工程化闭环。
