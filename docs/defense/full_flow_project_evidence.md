# FinAudit-Graph 全流程项目答辩证据

## 一、全流程结论

FinAudit-Graph 已覆盖“数据标注 → 模型训练/微调 → 应用开发 → Neo4j 图谱检索 → N8N 自动化”的完整链路，可以按全流程项目进行答辩展示。

```text
Label Studio 标注审计风险数据
→ LLaMA Factory LoRA 微调实验
→ FastAPI + Streamlit + LangGraph 审计应用
→ Chroma RAG + Neo4j 关联方图谱写入/关系穿透 + JSON fallback
→ N8N 邮件通知与复核任务自动化
```

## 二、评分标准映射

| 评分维度 | 项目证据 | 可展示文件/功能 |
| --- | --- | --- |
| 项目完整性 | 支持材料上传、解析、安全检查、风险识别、报告生成、自动化通知 | `src/finaudit_graph/interfaces/streamlit_app.py`、`src/finaudit_graph/core/service.py` |
| 技术深度 | 使用 LangGraph、LangChain Agent、RAG、向量库、Neo4j 关联方图谱、多智能体协商 | `src/finaudit_graph/core/workflow.py`、`src/finaudit_graph/retrieval/vector_store.py`、`src/finaudit_graph/retrieval/graph_store.py`、`src/finaudit_graph/intelligence/negotiation.py` |
| 创新性 | 面向财务审计场景，将财务指标异常、审计准则、关联方线索和复核自动化结合 | `data/demo_inputs/realistic_business_financials.xlsx`、`data/rag/audit_standards.json` |
| 答辩表现 | 有可运行前端、API、报告、N8N 邮件通知和复核任务状态 | Streamlit 页面、N8N 工作流、`data/outputs/*.md` |

## 三、全流程证据链

### 1. 数据标注

- 标注工具：Label Studio
- 标注数据：80 条审计风险样本
- 标注内容：
  - 最终风险类型
  - 关键财务指标
  - 异常审计表现
  - 涉案金额
  - 管理层抗辩理由

证据文件：

```text
archive/labelstudio_exports/project-36-at-2026-06-03-12-25-45eec0b7.json
archive/labelstudio_exports/labeling_screenshot.png
```

### 2. 模型训练/微调

- 微调方式：LoRA
- 训练工具：LLaMA Factory
- 基座模型：Qwen2.5-1.5B-Instruct
- 训练样本数：80

证据文件：

```text
data/lora_adapter/adapter_model.safetensors
data/lora_adapter/adapter_config.json
data/lora_adapter/artifact_summary.json
```

命令行展示：

```powershell
python -m finaudit_graph --lora-summary
```

### 3. 应用开发

应用层包括：

- FastAPI：后端 API
- Streamlit：演示前端
- LangGraph：四节点审计工作流
- Chroma：本地审计准则 RAG
- Neo4j/JSON：关联方图谱写入、关系穿透检索与 fallback
- Markdown/DOCX：审计报告输出

核心流程：

```text
财务材料输入
→ 安全检查
→ 文档/表格解析
→ Neo4j 图谱写入/关系穿透与 RAG 检索
→ 风险识别与多智能体协商
→ 审计报告生成
```

### 4. Neo4j 关联方图谱

Neo4j 图谱流程：

```text
材料解析完成
→ 规则抽取 Company / Person 节点和交易关系
→ 配置 Neo4j 时写入节点与 CONTROLLED_BY / PURCHASES_FROM / HAS_RECEIVABLE_FROM / RELATED_TO 等关系
→ 查询 1-3 跳关系路径
→ 返回关联方线索、穿透深度、证据和 graph_source
→ Neo4j 不可用或无结果时回退 data/graph/related_parties.json
```

证据文件：

```text
src/finaudit_graph/retrieval/graph_store.py
src/finaudit_graph/core/nodes.py
data/graph/init_neo4j.cypher
data/graph/related_parties.json
tests/test_workflow.py
```

可展示状态字段：

```text
neo4j_configured
neo4j_available
graph_write_status
graph_records_written
graph_source
```

### 5. N8N 自动化

N8N 工作流：

```text
integrations/n8n/finaudit_email_review_workflow.json
```

自动化流程：

```text
审计完成
→ POST 到 /webhook/finaudit-review
→ 判断 high_risk_count
→ 高风险时发送复核邮件
→ 生成 review_task_id
→ 返回 review_status / review_priority
→ Streamlit 展示自动化通知状态
```

当前真实工作流：

```text
FinAudit-Graph 审计复核邮件通知
workflow id: rs0jSHvNCb0gYeWo
```

## 四、推荐答辩演示顺序

1. 展示 Label Studio 标注截图和导出 JSON，说明数据来源和标注字段。
2. 展示 LoRA adapter 摘要，说明完成过领域微调实验。
3. 启动 FastAPI 和 Streamlit，上传真实业务化 Excel 样例。
4. 展示系统自动解析出的财务指标、Neo4j/图谱写入状态和关联方穿透结果。
5. 展示风险识别结果和生成的 Markdown/DOCX 审计报告。
6. 展示 Streamlit 中的“自动化通知状态”。
7. 切到 N8N，展示邮件通知工作流和最近成功执行记录。
8. 打开邮箱，展示收到的审计复核提醒邮件。

## 五、答辩话术

本项目不是单一的大模型调用，而是覆盖了大模型应用开发的完整生命周期。前期使用 Label Studio 对审计风险文本进行结构化标注，并完成 LoRA 微调实验；应用层使用 FastAPI 和 Streamlit 构建可运行系统，使用 LangGraph 编排审计流程，结合 Chroma RAG、Neo4j 关联方图谱和多智能体协商完成风险识别；最后通过 N8N 将高风险审计结果自动转为邮件复核任务，形成从数据、模型、应用、图谱检索到自动化复核的完整闭环。

## 六、当前可改进但不影响达标的点

- LoRA adapter 当前定位为训练成果展示和可选风险助手，主流程仍以 LangGraph、RAG、DeepSeek API 和本地规则为主。
- Neo4j 已支持真实图数据库写入和关系穿透查询；为保证答辩现场稳定，保留本地 JSON fallback。
- N8N 当前使用邮件作为复核通知渠道，后续可扩展飞书、多维表格或工单系统。
