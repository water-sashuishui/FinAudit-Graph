# FinAudit-Graph MVP 使用说明

本文档用于快速运行当前 MVP，并作为答辩演示时的操作顺序参考。

## 1. 环境准备

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

如果已经完成 editable install，后续直接在项目根目录运行命令即可。

```powershell
.\.venv\Scripts\Activate.ps1
```

## 1.1 DeepSeek 配置

项目会自动读取根目录 `.env`。DeepSeek 使用 OpenAI-compatible chat completions 格式：

```text
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
AUDIT_LLM_MODEL=deepseek-chat
```

请求头格式：

```text
Authorization: Bearer <DEEPSEEK_API_KEY>
Content-Type: application/json
```

如果 DeepSeek key 未配置、网络超时或 JSON 格式不符合要求，系统会自动使用本地规则版 `Compliance_Checker`，保证演示不中断。

配置 DeepSeek 后，`Compliance_Checker` 会优先使用 LangChain 1.x Agent。该 Agent 以 DeepSeek 为基座模型，并可调用财务指标分析、RAG 准则检索和关联方线索工具；如果 Agent 失败，再回退到 DeepSeek 直接调用或本地规则。

## 2. 查看 LoRA 成果

```powershell
python -m finaudit_graph --lora-summary
```

预期能看到：

- `artifact_type`: `LoRA adapter`
- `base_model`: `Qwen2.5-1.5B-Instruct`
- `train_samples`: `80`
- `train_loss`: `1.4076`

## 3. 构建与查询 RAG 向量库

构建或重建本地持久化向量数据库：

```powershell
python -m finaudit_graph --build-rag-index
```

预期看到：

```text
vector_store: data\rag\vector_store.json
embedding_model: local_hashing_v1
records: 4
```

查询审计准则向量库：

```powershell
python -m finaudit_graph --rag-query "收入增长和应收账款异常，需要关注截止性"
```

预期第一条命中通常是 `revenue-recognition`，并带有 `retrieval_mode: vector` 和 `similarity`。

## 4. 运行审计流程

```powershell
python -m finaudit_graph --demo
```

该命令会运行四节点流程：

1. `Data_Parser`：解析审计材料并生成模拟财务指标。
2. `Graph_Searcher`：读取关联方样本，模拟 Neo4j 穿透查询。
3. `Compliance_Checker`：优先运行 LangChain DeepSeek Agent；Agent 会调用财务指标、RAG 准则和关联方工具，失败时回退 DeepSeek 直接调用或本地规则版风险点。
4. `Report_Generator`：汇总为审计结论。

## 5. 生成报告

```powershell
python -m finaudit_graph --demo --save-report
```

输出文件位于：

```text
outputs/
```

包括 Markdown 报告和 DOCX 报告。

## 6. 运行 Streamlit 前端

```powershell
python -m streamlit run apps/streamlit_app.py
```

页面能力：

- 上传财报、合同或问询函材料，支持 `.pdf`、`.docx`、`.txt`、`.xlsx`、`.xls`、`.csv`。
- 点击按钮触发审计分析。
- 展示正式 Markdown 审计报告。
- 展示 N8N dry-run 或真实 webhook 返回结果。
- 下载 Markdown 报告和 N8N payload。

Excel/CSV 解析说明：

- 系统会识别“公司名称、被审计单位、会计年度、营业收入同比、主营业务收入增长、经营活动现金流同比、综合毛利率、应收账款同比”等常见字段别名。
- 如果指标名和数值在相邻单元格，系统会通过语义对齐和邻近单元格取值抽取字段。
- 解析结果会保留 `extraction_evidence`，用于说明字段来自哪个 sheet 和单元格。

## 7. N8N/飞书说明

当前 MVP 默认使用 dry-run 模式。如果需要接入真实 N8N，在 `.env` 中配置：

```text
N8N_WEBHOOK_URL=https://your-n8n-webhook-url
```

如果需要真实写入飞书，还需要确认：

```text
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_BASE_APP_TOKEN=
FEISHU_TABLE_ID=
```

飞书多维表格写入建议字段：

| 字段 | 类型 |
| --- | --- |
| 企业名称 | 文本 |
| 报告年度 | 数字 |
| 风险类型 | 多选 |
| 风险等级 | 单选 |
| 涉及关联方 | 文本 |
| 审计依据 | 长文本 |
| 整改建议 | 长文本 |
| 跟进状态 | 单选 |

## 8. 答辩演示顺序

1. 打开 README，说明项目目标和工程结构。
2. 展示 `model_artifacts/lora_adapter/`，说明 LoRA 微调成果。
3. 执行 `python -m finaudit_graph --lora-summary`。
4. 执行 `python -m finaudit_graph --build-rag-index` 和 `python -m finaudit_graph --rag-query "收入增长和应收账款异常，需要关注截止性"`。
5. 执行 `python -m finaudit_graph --demo --save-report`。
6. 展示 `outputs/` 中的报告。
7. 打开 Streamlit 页面做面向审计用户的可视化演示。
8. 说明当前 Neo4j/N8N 是稳定 fallback，RAG 已完成本地向量数据库，后续可升级为 Chroma/FAISS。
