# 009 Claim-Level Grounding 能力卡

## 目标

对008已经保存的60条 MiMo Formal 回答进行完全离线的最小事实声明审计，判断“Citation Support高但Unsupported Claim高”究竟是模型额外编造，还是旧评测器把合法改写误判为无依据。

## 输入与保护

- 输入固定为008的60条结果、Evidence Packet、Query和原始指标。
- 008结果、Manifest、Prompt、Context和 `evaluation_dataset_v2` 均未覆盖或重新评分。
- 审计脚本不访问网络，不读取或发送凭据，不改变模型、检索器或Prompt。

## 结果

- 共拆出117条声明，其中96条事实声明、21条拒答/说明性文字。
- 旧评测器标记的63条声明全部能在引用Evidence中找到同一事实锚点，判为 `evaluator_false_positive`。
- 离线审计没有发现 `unsupported_harmless`、`unsupported_material` 或 `contradicted`。
- 因此009云端复测未启动；`mimo_009_claim_grounding_v1` 只作为预留批次名。

## 边界

本轮只证明评测口径存在明显问题，不证明新Claim Schema已经经过MiMo API验证，也不改变008的原始结论或指标文件。
