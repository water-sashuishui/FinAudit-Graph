# FinAudit-Graph

FinAudit-Graph 是一个面向财务审计场景的智能分析 MVP。系统支持上传财务材料，自动抽取关键财务指标，结合审计准则 RAG、Neo4j 关联方图谱、LLM Agent 和本地规则识别审计风险，最后生成结构化审计报告。

当前系统采用 **FastAPI + Streamlit 共存**：

- `FastAPI`：后端服务与接口层。
- `Streamlit`：演示前端，负责上传材料、触发分析和展示结果。

## 核心流程

```text
财务材料输入 → 安全检查 → 材料解析 → Neo4j 图谱写入/检索 → RAG/模型分析 → 风险协商 → 报告输出
```

- 财务材料输入：支持 `txt / pdf / docx / xlsx / xls / csv`。
- 安全检查：识别敏感信息和 Prompt Injection，必要时阻断自动审计。
- 材料解析：从文本或表格中提取企业名称、年度、收入增长率、现金流增长率、毛利率、应收账款增长率等字段。
- 图谱检索：从上传材料中抽取企业、人员和交易关系线索，配置 Neo4j 时写入图数据库并优先做关系穿透查询；Neo4j 不可用时回退到本地 JSON 图谱样例。
- 智能分析：结合 LangGraph 工作流、LangChain Agent、DeepSeek API、Chroma RAG、Neo4j 关联方图谱和本地规则。
- 风险识别：覆盖收入异常、现金流异常、应收账款异常、毛利率异常、关联方交易等风险。
- 报告输出：生成 Markdown / DOCX 报告，并支持 N8N 邮件通知与复核任务状态回显。

## 项目结构

```text
FinAudit-Graph/
├─ data/
│  ├─ demo_inputs/          # 演示输入材料
│  ├─ eval_dataset.json     # 本地评测集
│  ├─ graph/                # 关联方图谱数据与 Neo4j 初始化脚本
│  ├─ lora_adapter/         # LoRA adapter 展示产物
│  ├─ outputs/              # 报告输出目录
│  ├─ rag/                  # 审计准则 RAG 数据与向量库
│  └─ raw/                  # 上传原始材料缓存
├─ src/
│  └─ finaudit_graph/
│     ├─ interfaces/        # FastAPI / CLI / Streamlit 对外入口
│     ├─ core/              # 服务总调度、工作流、节点和状态
│     ├─ ingestion/         # 文档解析与安全检查
│     ├─ retrieval/         # 审计准则 RAG、Neo4j 图谱写入和关联方检索
│     ├─ intelligence/      # LLM、Agent、LoRA、多智能体协商
│     ├─ outputs/           # 报告生成和 N8N 自动化通知
│     ├─ evaluation/        # 本地评测和演示数据生成
│     └─ settings.py        # 全局配置
├─ config/
│  └─ .env.example          # 环境变量模板
├─ docs/
│  └─ defense/              # 全流程项目答辩证据与演示说明
├─ integrations/
│  └─ n8n/                  # N8N 工作流 JSON
├─ tests/
│  ├─ test_api.py
│  └─ test_workflow.py
├─ archive/                 # 历史归档，保留不参与主流程
├─ pyproject.toml           # Python 包配置，保留在根目录便于安装
├─ requirements.txt         # 依赖列表，保留在根目录便于安装
└─ README.md
```

## 环境准备

复制环境变量模板到项目根目录：

```powershell
copy config\.env.example .env
```

关键配置示例：

```text
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
AUDIT_LLM_MODEL=deepseek-chat
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
N8N_WEBHOOK_URL=http://localhost:5678/webhook/finaudit-review
AUDIT_REVIEW_EMAIL=your_review_email@example.com
```

> `NEO4J_PASSWORD=password` 是模板占位值，系统会视为未真正配置 Neo4j，并自动使用本地 JSON fallback。演示真实 Neo4j 时请改成你本机 Neo4j 的实际密码。

安装依赖：

```powershell
pip install -r requirements.txt
pip install -e .
```

## 演示启动方式

演示时建议同时启动后端和前端。

### 1. 启动 FastAPI 后端

```powershell
python -m uvicorn finaudit_graph.interfaces.api:app --reload
```

本地地址：

- Swagger 文档页：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON：[http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

### 2. 启动 Streamlit 前端

```powershell
python -m streamlit run src/finaudit_graph/interfaces/streamlit_app.py
```

本地地址通常为：

- [http://localhost:8501](http://localhost:8501)

如果 `8501` 端口被占用，可以改用：

```powershell
python -m streamlit run src/finaudit_graph/interfaces/streamlit_app.py --server.port 8506
```

## 推荐演示顺序

1. 启动 FastAPI。
2. 打开 Swagger，确认接口可用。
3. 启动 Streamlit。
4. 上传 `data/demo_inputs/sample_financial_data.xlsx` 或其他演示材料。
5. 展示 Neo4j/图谱状态：是否配置、是否可连接、写入状态、写入记录数和图谱来源。
6. 展示报告、风险识别结果和下载能力。
7. 如需展示 N8N 加分项，启用 `FinAudit-Graph 审计复核邮件通知` 工作流，并在 `.env` 中配置 `N8N_WEBHOOK_URL` 和 `AUDIT_REVIEW_EMAIL`。
8. 在 Streamlit 右侧查看“自动化通知状态”，确认高风险结果是否已通过 N8N 邮件通知复核人。
9. 展示 LoRA adapter 摘要作为微调成果补充。

## N8N 邮件通知工作流

项目提供了可导入 N8N 的邮件通知工作流：

```text
integrations/n8n/finaudit_email_review_workflow.json
```

工作流逻辑：

```text
FinAudit-Graph 审计完成
→ POST 到 N8N Webhook
→ 判断 high_risk_count 是否大于 0
→ 高风险时使用 `163邮箱SMTP` 凭证发送复核邮件
→ 无高风险或未配置收件人时返回跳过通知
→ 返回 review_task_id / review_status / review_priority
→ FastAPI 将 N8N 响应整理为结构化 n8n_result
→ Streamlit 展示通知结果、通知模式、说明和高风险数量
```

默认 Webhook 地址：

```text
http://localhost:5678/webhook/finaudit-review
```

邮件收件人不写死在工作流中，由项目 `.env` 中的 `AUDIT_REVIEW_EMAIL` 提供。

## Neo4j 关联方图谱

Neo4j 在项目中负责把上传材料里的企业、人员和交易关系变成可查询的关系网，用于发现潜在关联方风险。

当前实现包括：

- 从解析后的财务材料中规则抽取 `Company`、`Person` 节点。
- 写入 `CONTROLLED_BY`、`PURCHASES_FROM`、`HAS_RECEIVABLE_FROM`、`RELATED_TO` 等关系。
- 查询 1 到 3 跳关系路径，识别隐藏控制、资金往来、供应商采购和关联方线索。
- 在工作流状态中返回 `neo4j_configured`、`neo4j_available`、`graph_write_status`、`graph_records_written` 和 `graph_source`。
- Neo4j 未配置、连接失败或查询为空时，自动回退到 `data/graph/related_parties.json`，保证答辩演示可继续运行。

可选初始化脚本：

```text
data/graph/init_neo4j.cypher
```

答辩表达建议：

```text
Neo4j 不是单独展示的数据库，而是接在材料解析之后。系统先从上传文件中抽取企业和关系线索，配置 Neo4j 时写入图数据库并做关系穿透查询；如果现场 Neo4j 不可用，就自动回退到 JSON 样例，保证主流程稳定。
```

## 全流程项目证据

本项目可按“数据标注 → 模型训练/微调 → 应用开发 → Neo4j 图谱检索 → N8N 自动化”的全流程项目进行答辩。证据链和演示顺序见：

```text
docs/defense/full_flow_project_evidence.md
```

对应流程：

```text
Label Studio 审计风险数据标注
→ LLaMA Factory LoRA 微调实验
→ FastAPI + Streamlit + LangGraph 应用开发
→ Chroma RAG + Neo4j 图谱写入/关系穿透 + 多智能体协商
→ N8N 邮件通知与复核任务自动化
```

## FastAPI 接口

- `GET /api/health`
- `GET /api/config/status`
- `POST /api/rag/query`
- `POST /api/rag/rebuild`
- `POST /api/audit/run`

`POST /api/audit/run` 支持：

- 上传文件。
- 提交本地文件路径。

返回字段包括：

- `request_id`
- `status`
- `parsed_financial_data`
- `related_parties`
- `neo4j_configured`
- `neo4j_available`
- `graph_write_status`
- `graph_records_written`
- `graph_source`
- `audit_risks`
- `negotiation_trace`
- `llm_provider`
- `final_report_markdown`
- `n8n_result`
- `warnings`
- `security_flags`

## CLI 用法

重建 RAG 向量库：

```powershell
python -m finaudit_graph --build-rag-index
```

查询审计准则：

```powershell
python -m finaudit_graph --rag-query "收入增长和应收账款异常，需要关注什么风险"
```

运行 Demo：

```powershell
python -m finaudit_graph --demo
```

指定材料并保存报告：

```powershell
python -m finaudit_graph --demo --document data/demo_inputs/sample_financial_data.xlsx --save-report
```

运行评测：

```powershell
python -m finaudit_graph --run-eval
```

查看 LoRA 展示材料：

```powershell
python -m finaudit_graph --lora-summary
```

## LoRA 说明

当前项目保留了 LoRA 微调成果，但它的定位是：

- 展示领域数据微调实践。
- 用于答辩材料和训练成果说明。
- 通过命令行查看 adapter 摘要。

当前主流程的实际推理链路仍然是：

- LangGraph 工作流。
- LangChain Agent。
- DeepSeek API。
- Chroma RAG。
- Neo4j 关联方图谱。
- 本地规则 fallback。

LoRA adapter 文件位于：

```text
data/lora_adapter/
```

## 测试

```powershell
python -m unittest discover -s tests
```

也可以单独运行：

```powershell
python tests/test_workflow.py
python tests/test_api.py
```

## 评测与安全

- 评测集：`data/eval_dataset.json`
- 当前指标：
  - `retrieval_hit_rate`
  - `risk_recall`
  - `report_faithfulness`
- 安全能力：
  - 手机号 / 邮箱 / 身份证 / 银行账号脱敏。
  - Prompt Injection 规则拦截。
  - 命中注入时返回 `blocked_for_review`。
