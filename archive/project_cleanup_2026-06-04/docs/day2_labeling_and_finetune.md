# Day 2 数据标注与微调演示说明

## 目标

Day 2 的目标不是追求大规模真实训练，而是建立一条能在答辩中讲清楚的数据增强链路：审计文本样本进入 Label Studio 标注，形成风险分类和实体识别结果，再转化为 LLaMA Factory 可用的监督微调样本。

## 标注任务

- 数据文件：`data/labeling/audit_risk_samples.jsonl`
- 标注配置：`data/labeling/label_studio_config.xml`
- 任务类型：多标签风险分类、单选风险等级、关键实体标注

风险分类包括：

- 虚增收入
- 虚增利润
- 关联方利益输送
- 内控缺陷
- 资金占用
- 存货跌价风险
- 应收账款坏账风险
- 信息披露不充分

实体标签包括公司名称、交易对手、金额、年份和审计线索。

## Label Studio 演示步骤

1. 新建项目，命名为 `FinAudit-Graph 审计风险标注`。
2. 粘贴 `label_studio_config.xml` 中的标注界面配置。
3. 导入 `audit_risk_samples.jsonl`。
4. 选择 5 到 10 条样本做现场标注演示。
5. 导出 JSON 结果，用于说明后续 SFT 数据构造。

## LLaMA Factory 演示材料

- 数据集注册示例：`data/labeling/dataset_info.json`
- LoRA 配置示例：`configs/llama_factory/finaudit_lora_demo.yaml`

答辩时建议说明：

- 微调用于增强模型对审计风险类型、风险等级和专业表达的敏感度。
- 7 天冲刺期内可以用小样本证明流程，主系统仍可通过 API 模型和规则 fallback 保证演示稳定。
- 微调前后对比可以选取相同审计文本，让模型分别输出风险类型、依据和整改建议。

