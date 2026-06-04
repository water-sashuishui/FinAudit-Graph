# Label Studio 导入说明

## 导入哪个文件

请导入：

`data/labeling/audit_risk_samples_labelstudio.json`

不要导入：

`data/labeling/audit_risk_samples.jsonl`

原因是 Label Studio 的网页导入面板支持 `.json`，不直接支持 `.jsonl`。

## 标注界面配置

在 Label Studio 项目的 Labeling Interface 中粘贴：

`data/labeling/label_studio_config.xml`

该配置包含：

- 风险类型：虚增收入、虚增利润、关联方利益输送、内控缺陷、资金占用、存货跌价风险、应收账款坏账风险、信息披露不充分
- 风险等级：低、中、高
- 实体标签：公司名称、交易对手、金额、年份、审计线索

## 建议标注数量

先标注 20 到 50 条样本即可，用于毕设演示和后续生成微调样本。

