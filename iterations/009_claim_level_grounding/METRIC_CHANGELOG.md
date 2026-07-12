# 指标变更记录

## 来源保护

- `iterations/008_cloud_generation_upper_bound/metrics.json` 未修改。
- 008的60条结果、Manifest、Prompt、Context和评测集未覆盖。
- `metrics_v2.json` 是009离线审计视角的新增文件，不替换008原始指标。

## 变更原因

008把“引用Evidence中有同一事实但文字不是逐字复制”的声明计为Unsupported。009补充了声明级拆分，并同时检查正文、标题和标题路径，区分了真正无依据与评测器逐字匹配造成的误报。

## 结果差异

- 008旧标记：26/60回答含Unsupported标记。
- 009审计：63条被旧规则标记的最小声明均为 `evaluator_false_positive`。
- 009未发现真实 `unsupported_harmless`、`unsupported_material` 或 `contradicted` 声明。
- 因此修正视角的Claim-level Unsupported Rate、Material Unsupported Rate均为0%，不是对008结果的回写或重算伪装。

## API决策

由于评测器口径问题已超过20%阈值，009云端复测不启动；预留的 `mimo_009_claim_grounding_v1` 没有产生请求或费用。
