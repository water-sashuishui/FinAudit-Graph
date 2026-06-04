# FinAudit-Graph 答辩演示脚本

适用场景：5 到 8 分钟毕业设计演示。目标是让评委看到系统从“材料输入”到“风险输出”和“报告生成”的完整闭环。

## 0. 演示前准备

打开项目根目录：

```powershell
cd D:\LLM\FinAudit-Graph
.\.venv\Scripts\Activate.ps1
```

确认项目已安装：

```powershell
pip install -e .
```

预期结果：命令结束后没有报错，后续可以直接运行 `python -m finaudit_graph`。

## 1. 展示项目结构

打开 VSCode 资源管理器，展示根目录：

```text
apps/
archive/
configs/
data/
docs/
model_artifacts/
outputs/
scripts/
src/
tests/
```

讲解词：

> 项目采用标准 Python 工程结构。核心代码放在 `src/finaudit_graph`，前端入口放在 `apps`，演示数据放在 `data`，LoRA 训练产物放在 `model_artifacts`，计划书和过程材料统一归档到 `archive`。

预期看到：根目录没有中文命名文件，结构清晰。

## 2. 展示 LoRA 微调成果

运行：

```powershell
python -m finaudit_graph --lora-summary
```

讲解词：

> 这里展示的是 AutoDL 上通过 LLaMA Factory 训练得到的 LoRA adapter。它不是完整基座模型，而是适配器权重，训练数据来自 Label Studio 标注后的 80 条审计风险样本。

预期看到：

```text
artifact_type: LoRA adapter
base_model: Qwen2.5-1.5B-Instruct
train_samples: 80
train_loss: 1.4076
missing_required_files: []
```

## 3. 运行后端审计流程

运行：

```powershell
python -m finaudit_graph --demo --document data/raw/test_audit.txt --save-report
```

讲解词：

> 系统会读取上传材料，解析企业名称、报告年度和关键财务指标，然后经过 LangGraph 四个节点：数据解析、图谱检索、合规审查和报告生成。

预期看到：

```text
测试科技有限公司
2024
35.5%
Saved Markdown report: outputs\test_audit_audit_report.md
Saved DOCX report: outputs\test_audit_audit_report.docx
```

## 4. 打开前端演示页

运行：

```powershell
python -m streamlit run apps\streamlit_app.py
```

打开：

```text
http://localhost:8501
```

点击位置：

1. 点击上传区域，选择 `data/raw/test_audit.txt`。
2. 点击 `开始审计分析`。
3. 查看左侧审计报告。
4. 查看右侧自动化记录 JSON。
5. 点击下载 Markdown 报告或 N8N Payload。

讲解词：

> 前端面向审计用户，不展示 LoRA 等技术细节，只保留上传、分析、结果查看和下载。技术成果在 CLI 和答辩材料中展示，用户界面保持业务逻辑清晰。

预期看到：

- `企业合规风控审计报告`
- 企业名称：`测试科技有限公司`
- 报告年度：`2024`
- 风险点、整改建议和自动化记录 payload

## 5. 展示报告文件

打开：

```text
outputs/test_audit_audit_report.md
outputs/test_audit_audit_report.docx
```

讲解词：

> 系统不仅在页面展示结果，也会生成可交付的 Markdown 和 Word 报告，便于作为审计底稿或答辩证据留存。

## 6. 说明 fallback 设计

讲解词：

> 项目支持 DeepSeek API、Neo4j 和 N8N 真实接入。但为了保证答辩演示稳定，所有外部服务都有 fallback。DeepSeek 失败会回退到本地规则版风险判断，Neo4j 不可用会回退到本地图谱 JSON，N8N 未配置时会输出 dry-run payload。

## 7. 收尾总结

讲解词：

> FinAudit-Graph 的核心价值是把财务审计场景拆成可解释的多智能体流程，并结合模型微调、图谱穿透、RAG 准则依据和自动化记录，形成一个能运行、能解释、能扩展的端到端审计 MVP。
