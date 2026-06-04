# FinAudit-Graph

FinAudit-Graph 是一个面向毕业设计演示的智能财务审计与合规审查 MVP。当前系统采用 **FastAPI + Streamlit 共存** 的方式：

- `FastAPI` 作为主后端入口与服务接口层
- `Streamlit` 作为演示前端，专门调用 FastAPI 接口展示上传、分析和报告结果

## 当前能力

- `LangGraph` 四节点工作流：`Data_Parser -> Graph_Searcher -> Compliance_Checker -> Report_Generator`
- `LangChain 1.x Agent + DeepSeek`：在合规审查节点执行结构化风险判断
- `Chroma` 本地持久化向量数据库：用于审计准则 RAG 检索
- `Neo4j / JSON fallback`：用于关联方穿透分析
- 多格式材料解析：支持 `txt / pdf / docx / xlsx / xls / csv`
- `FastAPI`：主服务入口与 Swagger 调试入口
- `Streamlit`：调用 FastAPI 的演示前端
- `Markdown / DOCX` 报告生成
- `N8N dry-run / webhook` 自动化留痕

## 最小运行结构

```text
FinAudit-Graph/
├─ apps/
│  └─ streamlit_app.py
├─ data/
│  ├─ graph/
│  ├─ rag/
│  └─ raw/
├─ outputs/
├─ showcase/
│  ├─ demo_inputs/
│  ├─ lora_adapter/
│  └─ tests/
├─ src/
│  └─ finaudit_graph/
├─ .env
├─ .env.example
├─ .gitignore
├─ pyproject.toml
├─ requirements.txt
└─ README.md
```

说明：

- `archive/` 只保存历史材料与旧版本入口
- `apps/streamlit_app.py` 现在只负责调用 FastAPI，不再直接运行工作流
- `data/rag/chroma_db/` 可通过命令重建，因此已加入 `.gitignore`

## FastAPI 接口

- `GET /api/health`
- `GET /api/config/status`
- `POST /api/rag/query`
- `POST /api/rag/rebuild`
- `POST /api/audit/run`

`POST /api/audit/run` 同时支持：

- 上传文件
- 提交本地文件路径

返回字段包括：

- `request_id`
- `status`
- `parsed_financial_data`
- `related_parties`
- `audit_risks`
- `final_report_markdown`
- `n8n_result`
- `warnings`

## 环境配置

先复制环境变量模板：

```powershell
copy .env.example .env
```

关键配置示例：

```text
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
AUDIT_LLM_MODEL=deepseek-chat
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
N8N_WEBHOOK_URL=
```

## 安装依赖

```powershell
pip install -r requirements.txt
pip install -e .
```

## 启动方式

### 1. 启动 FastAPI 主服务

```powershell
python -m uvicorn finaudit_graph.api:app --reload
```

Swagger 地址：

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. 启动 Streamlit 演示前端

```powershell
python -m streamlit run apps/streamlit_app.py
```

说明：

- Streamlit 页面默认请求 `http://127.0.0.1:8000`
- 如果 FastAPI 换了端口，可以在页面顶部手动修改 API 地址

## CLI 用法

运行 demo：

```powershell
python -m finaudit_graph --demo
```

生成报告文件：

```powershell
python -m finaudit_graph --demo --save-report
```

查询审计准则：

```powershell
python -m finaudit_graph --rag-query "收入增长和应收账款异常，需要关注截止性"
```

重建 RAG 向量库：

```powershell
python -m finaudit_graph --build-rag-index
```

查看 LoRA 展示材料：

```powershell
python -m finaudit_graph --lora-summary
```

## 测试

```powershell
python showcase/tests/test_workflow.py
python showcase/tests/test_api.py
```

## 演示建议顺序

1. 先启动 FastAPI 并打开 Swagger
2. 用 `POST /api/rag/rebuild` 重建向量库
3. 用 `POST /api/audit/run` 验证后端接口
4. 再打开 Streamlit，做可视化上传和报告展示
5. 如需补充，再用 CLI 展示 RAG 查询和 LoRA 摘要
