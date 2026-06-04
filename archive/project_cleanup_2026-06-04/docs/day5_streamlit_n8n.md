# Day 5 Streamlit 与 N8N 自动化闭环说明

## 目标

Day 5 的目标是形成可演示的前端和自动化记录闭环：

1. Streamlit 上传审计材料。
2. 调用 FinAudit-Graph 四节点工作流。
3. 展示 Markdown 审计报告。
4. 生成 N8N Webhook payload。
5. 如果配置了 `N8N_WEBHOOK_URL`，则发送到 N8N；未配置时进入 dry-run，便于本地演示。

## 运行方式

```powershell
python -m streamlit run apps/streamlit_app.py
```

## N8N Payload 字段

- `company_name`：被审计企业名称。
- `reporting_year`：报告年度。
- `risk_count`：风险点数量。
- `high_risk_count`：高风险点数量。
- `risks`：风险明细。
- `related_parties`：潜在关联方。
- `final_audit_summary`：最终 Markdown 审计综述。

## 飞书多维表格建议字段

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
