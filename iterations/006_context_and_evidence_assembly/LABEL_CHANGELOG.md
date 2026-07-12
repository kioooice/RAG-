# LABEL_CHANGELOG

## 006-v2（2026-07-12）

- 保护对象：`iterations/005_grounded_generation/evaluation_dataset.jsonl`，未修改。
- 005 dataset SHA-256：`a61a515ebe6604c88293685519563a888c7b816cc8baa8b28922aa237af79555`。
- 变更：新建 `evaluation_dataset_v2.jsonl`，保留全部 Query、question_type、reference_answer、Required Facts、冲突事实和 Relevant Unit ID。
- 没有根据模型回答新增、删除或改写任何 Ground Truth。
- 新增内容仅为确定性审计元数据：`dataset_version`、`oracle_unit_ids_v2`、`oracle_evidence_map` 和标签保留说明，便于Evidence Packet追溯。
- 审计结论：20个可回答问题的Oracle Evidence Completeness为100%，不需要修正Relevant Unit标签。

## 禁止事项记录

- 未修改001—005结果。
- 未调整模型、BGE-M3、Top-K或生成参数。
- 未使用模型输出反向选择Evidence或修改标签。
