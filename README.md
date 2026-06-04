# FinAudit-Graph

FinAudit-Graph 是一个面向毕业设计演示的端到端智能财务审计与合规审查 MVP。系统围绕“上传审计材料 -> LangGraph 多智能体分析 -> Neo4j/RAG 增强 -> 风险识别 -> N8N 自动化记录 -> 报告生成”的闭环展开，重点展示可运行、可解释、可答辩的智能审计原型。

## MVP 已具备的能力

- **四节点智能体流程**：`Data_Parser -> Graph_Searcher -> Compliance_Checker -> Report_Generator`。
- **审计风险识别**：输出风险类型、风险等级、审计依据和整改建议。
- **LangChain DeepSeek Agent**：`.env` 配置 DeepSeek 后，`Compliance_Checker` 会优先创建 LangChain 1.x Agent，由 Agent 调用财务指标、RAG 检索和关联方工具完成风险判断；失败时回退 DeepSeek 直接调用或本地规则版。
- **真实文件解析与语义对齐**：支持上传 `.txt`、`.pdf`、`.docx`、`.xlsx`、`.xls`、`.csv`；Excel/CSV 会按字段别名和邻近单元格做财务指标语义对齐，抽取不足时自动补 demo 值。
- **图谱增强 fallback**：使用 `data/graph/related_parties.json` 模拟 Neo4j 关联方穿透结果，并保留 Cypher 初始化脚本。
- **本地向量数据库 RAG**：使用 `data/rag/audit_standards.json` 构建 `data/rag/vector_store.json`，优先按向量相似度检索审计准则片段；异常时回退关键词检索。
- **LoRA 微调成果展示**：`model_artifacts/lora_adapter/` 已保存 AutoDL 训练得到的 LoRA adapter。
- **Streamlit 前端**：支持上传材料、触发分析、展示报告、下载结果和查看 N8N payload。
- **N8N dry-run**：未配置真实 webhook 时仍能生成结构化自动化记录 payload。
- **报告生成**：支持 Markdown 和 DOCX 审计报告落盘。

## 工程结构

```text
FinAudit-Graph/
├─ apps/
│  └─ streamlit_app.py
├─ archive/
│  └─ project_cleanup_2026-06-04/
├─ data/
│  ├─ graph/
│  ├─ rag/
│  └─ raw/
├─ model_artifacts/
│  └─ lora_adapter/
├─ outputs/
├─ src/
│  └─ finaudit_graph/
├─ tests/
│  └─ test_workflow.py
├─ README.md
├─ pyproject.toml
└─ requirements.txt
```

说明：过程材料、旧报告、训练日志、Label Studio 导出、答辩包装材料和辅助脚本已统一移动到 `archive/project_cleanup_2026-06-04/`。根目录只保留支持运行、测试和基础演示的文件。

## LoRA 微调成果

LoRA 产物位于：

```text
model_artifacts/lora_adapter/
```

关键文件：

- `adapter_model.safetensors`：LoRA adapter 权重
- `adapter_config.json`：LoRA adapter 配置
- `artifact_summary.json`：当前项目整理后的产物说明

训练日志、loss 曲线、SFT 数据和 LLaMA Factory 配置已归档到 `archive/project_cleanup_2026-06-04/training_materials/`，不再放在运行态目录中。

当前训练摘要：

| 项目 | 内容 |
| --- | --- |
| 基座模型 | Qwen2.5-1.5B-Instruct |
| 微调方式 | LoRA |
| 训练数据 | 80 条审计风险 SFT 样本 |
| epoch | 2 |
| train_loss | 1.4076 |
| 训练耗时 | 约 52 秒 |
| 产物性质 | LoRA adapter，不包含完整基座模型 |

查看 LoRA 成果摘要：

```powershell
python -m finaudit_graph --lora-summary
```

## RAG 向量数据库

审计准则知识库位于：

```text
data/rag/audit_standards.json
```

本地持久化向量库位于：

```text
data/rag/vector_store.json
```

构建或重建向量库：

```powershell
python -m finaudit_graph --build-rag-index
```

查询向量库：

```powershell
python -m finaudit_graph --rag-query "收入增长和应收账款异常，需要关注截止性"
```

说明：当前 MVP 使用 `local_hashing_v1` 本地文本向量方式，优点是无需下载 embedding 模型、无需联网、答辩现场稳定可复现。后续生产化可以将该层替换为 Chroma、FAISS 或云端 embedding 服务。

## 快速运行

复制并填写环境变量：

```powershell
copy .env.example .env
```

DeepSeek 配置格式：

```text
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
AUDIT_LLM_MODEL=deepseek-chat
```

说明：代码会按 OpenAI-compatible chat completions 格式请求 DeepSeek，即 `Authorization: Bearer <DEEPSEEK_API_KEY>`。如果 key 缺失、网络失败或返回格式不符合要求，系统会自动回退到本地规则版风险判断。

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

运行 CLI 审计演示：

```powershell
python -m finaudit_graph --demo
```

说明：如果 `.env` 中配置了 `DEEPSEEK_API_KEY`，合规审查节点会优先走 LangChain DeepSeek Agent；如果未配置 key、网络失败或 Agent 返回格式异常，系统会自动回退，保证演示不中断。

使用 Excel/CSV 财务数据演示：

```powershell
python -m finaudit_graph --demo --document data/raw/your_financial_data.xlsx --save-report
```

生成 Markdown/DOCX 报告：

```powershell
python -m finaudit_graph --demo --save-report
```

运行 Streamlit MVP：

```powershell
python -m streamlit run apps/streamlit_app.py
```

运行测试：

```powershell
.\.venv\Scripts\python.exe tests\test_workflow.py
```

## 当前完成度

| 阶段 | 计划目标 | MVP 状态 |
| --- | --- | --- |
| Day 1 | 工程初始化、目录结构、README、依赖 | 已完成 |
| Day 2 | Label Studio 标注、SFT 数据、LoRA 配置 | 已完成，并已有 LoRA adapter 训练产物 |
| Day 3 | LangGraph 四节点核心流程 | 已完成，测试通过 |
| Day 4 | Neo4j 与 RAG 增强 | 已完成 Neo4j JSON fallback 与本地持久化向量数据库 RAG |
| Day 5 | Streamlit、N8N、飞书闭环 | 已完成 Streamlit、DeepSeek 可选调用与 N8N dry-run，真实飞书写入待扩展 |
| Day 6 | 报告生成与联调 | 已完成 Markdown/DOCX 报告生成 |
| Day 7 | PPT、演示视频、答辩稿、FAQ | 已有答辩文档框架，正式材料待制作 |

## 演示主线

1. 展示 README 和计划书归档，说明项目目标与技术路线。
2. 展示 `data/labeling/` 和 `model_artifacts/lora_adapter/`，说明标注到 LoRA 微调闭环。
3. 运行 `python -m finaudit_graph --lora-summary`，证明训练产物已整理。
4. 运行 `python -m finaudit_graph --demo --save-report`，展示智能审计报告。
5. 打开 Streamlit 页面，演示上传、分析、报告展示和 N8N dry-run payload。
6. 讲解 Neo4j fallback 与本地向量数据库 RAG 如何保证演示稳定，以及后续如何替换为真实服务。

## 重要文档

- `docs/mvp_usage.md`：MVP 运行与演示说明
- `docs/project_status.md`：项目完成度与待完善事项
- `docs/day7_defense_package.md`：答辩 PPT 结构、演示脚本和 FAQ
- `archive/planning_docs/`：计划书、规划书和计划书生成脚本归档

## 后续可增强项

- 扩展 Excel 多表、多期间和复杂合并单元格的财务语义对齐能力。
- 接入真实 Neo4j Driver 查询，替换 JSON fallback。
- 将本地向量库升级为 FAISS/Chroma，并接入更强的 embedding 模型。
- 配置真实 `N8N_WEBHOOK_URL` 和飞书多维表格 token。
- 增加 LoRA adapter 本地推理对比脚本，展示微调前后效果。
- 制作最终 PPT、演示视频和答辩稿。
