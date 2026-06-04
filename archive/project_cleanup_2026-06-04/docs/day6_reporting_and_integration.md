# Day 6 报告生成与联调说明

## 目标

Day 6 的目标是把智能体输出固化为可交付报告，并为端到端联调留出稳定命令。

## 报告输出

运行：

```powershell
python -m finaudit_graph --demo --save-report
```

输出位置：

- `outputs/*_audit_report.md`
- `outputs/*_audit_report.docx`，仅在安装 `python-docx` 时生成

## 联调检查

- CLI 能输出 Markdown 审计综述。
- 报告文件能落盘到 `outputs/`。
- Streamlit 页面能调用同一条工作流。
- N8N Webhook 未配置时进入 dry-run，配置后发送结构化 JSON。
