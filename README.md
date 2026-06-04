# FinAudit-Graph

FinAudit-Graph 是一个面向毕业设计演示的智能财务助手 / 审计分析 MVP。  
当前系统采用 **FastAPI + Streamlit 共存** 的方式：

- `FastAPI` 作为后端服务与接口层
- `Streamlit` 作为演示前端，负责上传材料、触发分析和展示结果

## 当前能力

- 多格式材料解析：`txt / pdf / docx / xlsx / xls / csv`
- 审计准则 RAG：基于 `Chroma` 本地持久化向量库
- 财务风险识别：`LangGraph` 四节点工作流
- 多智能体协商：`Risk / Evidence / Recommendation`
- 报告生成：`Markdown / DOCX`
- 自动化记录：`N8N dry-run / webhook`
- 评测与安全防护：
  - 本地评测集
  - PII 脱敏
  - Prompt Injection 拦截

## 项目结构

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
│  ├─ eval_dataset.json
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

## 环境准备

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

安装依赖：

```powershell
pip install -r requirements.txt
pip install -e .
```

## 演示启动方式

**注意：演示时需要同时启动两个服务。**

### 1. 启动 FastAPI 后端

```powershell
python -m uvicorn finaudit_graph.api:app --reload
```

本地地址：

- Swagger 文档页：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON：[http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

### 2. 启动 Streamlit 前端

```powershell
python -m streamlit run apps/streamlit_app.py
```

本地地址通常为：

- [http://localhost:8501](http://localhost:8501)

如果 `8501` 端口被占用，可以改用：

```powershell
python -m streamlit run apps/streamlit_app.py --server.port 8506
```

对应地址：

- [http://localhost:8506](http://localhost:8506)

## 推荐演示顺序

1. 先启动 FastAPI
2. 打开 Swagger，确认接口可用
3. 再启动 Streamlit
4. 在 Streamlit 页面上传财务材料并执行分析
5. 展示报告、风险识别结果和下载能力

## FastAPI 接口

- `GET /api/health`
- `GET /api/config/status`
- `POST /api/rag/query`
- `POST /api/rag/rebuild`
- `POST /api/audit/run`

`POST /api/audit/run` 支持：

- 上传文件
- 提交本地文件路径

返回字段包括：

- `request_id`
- `status`
- `parsed_financial_data`
- `related_parties`
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
python -m finaudit_graph --demo --document showcase/demo_inputs/sample_financial_data.xlsx --save-report
```

运行评测：

```powershell
python -m finaudit_graph --run-eval
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

## 评测与安全

- 评测集：`showcase/eval_dataset.json`
- 当前指标：
  - `retrieval_hit_rate`
  - `risk_recall`
  - `report_faithfulness`
- 安全能力：
  - 手机号 / 邮箱 / 身份证 / 银行账号脱敏
  - Prompt Injection 规则拦截
  - 命中注入时返回 `blocked_for_review`
