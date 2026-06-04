# FinAudit-Graph 云端微调材料说明

## 文件清单

- `audit_risk_sft_from_labelstudio_80.jsonl`：80 条人工标注转换后的 SFT 数据。
- `dataset_info.json`：LLaMA Factory 自定义数据集注册文件。
- `finaudit_lora_demo.yaml`：LoRA/SFT 训练配置。

## 推荐使用方式

将本文件夹中的文件上传到云端 LLaMA Factory 环境。

推荐放置方式：

```text
LLaMA-Factory/
  data/
    audit_risk_sft_from_labelstudio_80.jsonl
    dataset_info.json
  configs/
    finaudit_lora_demo.yaml
```

训练前确认 `finaudit_lora_demo.yaml` 中：

```yaml
dataset: finaudit_audit_risk_labelstudio_80
template: qwen
finetuning_type: lora
```

云端训练命令示例：

```bash
llamafactory-cli train configs/finaudit_lora_demo.yaml
```

本地不要运行训练脚本。
