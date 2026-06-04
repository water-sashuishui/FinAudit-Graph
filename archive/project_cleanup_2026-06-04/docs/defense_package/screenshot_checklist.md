# 截图留证清单

建议答辩前截图并保存到 `docs/defense_package/evidence/`。

## 必备截图

1. **前端首页**
   - 打开 `http://localhost:8501`
   - 截图内容：标题、上传区域、开始分析按钮
   - 建议文件名：`frontend_home.png`

2. **前端分析结果**
   - 上传 `data/raw/test_audit.txt`
   - 点击 `开始审计分析`
   - 截图内容：审计报告、自动化记录、下载按钮
   - 建议文件名：`frontend_analysis.png`

3. **LoRA 摘要**
   - 运行 `python -m finaudit_graph --lora-summary`
   - 截图内容：`LoRA adapter`、`Qwen2.5-1.5B-Instruct`、`train_samples=80`
   - 建议文件名：`lora_summary.png`

4. **测试通过**
   - 运行 `python tests/test_workflow.py`
   - 截图内容：`Ran 12 tests` 和 `OK`
   - 建议文件名：`tests_ok.png`

5. **报告文件**
   - 展示 `outputs/test_audit_audit_report.md`
   - 展示 `outputs/test_audit_audit_report.docx`
   - 建议文件名：`report_files.png`

## 已生成文字证据

当前目录下已经生成：

- `evidence/test_workflow_output.txt`
- `evidence/lora_summary.json`
- `evidence/demo_cli_output.txt`

如果截图工具不稳定，可以用这些文字证据作为兜底材料。
