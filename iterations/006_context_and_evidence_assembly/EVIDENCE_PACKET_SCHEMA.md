# Evidence Packet Schema（evidence-packet-v0.1）

每个输入 KnowledgeUnit 按检索/Oracle 的确定性顺序序列化为一个 Evidence。重复文本只保留首次出现的 KnowledgeUnit，后续 ID 记录在 `duplicate_ids`；超过固定字符预算的单元记录在 `truncated_ids`，不得静默丢弃。

```text
[Evidence E1]
knowledge_unit_id: <KnowledgeUnit ID>
document_id: <原始 Document ID>
title: <标题>
title_path: <JSON 数组>
source_locator: <JSON 对象>
unit_type: <类型>
content: <原始文本，不改写>
```

约束：

- `Evidence E#` 与 `knowledge_unit_id` 一一映射；模型只能引用真实的 `knowledge_unit_id`。
- `document_id`、标题路径、页码/工作表/幻灯片/单元格范围等 `source_locator` 原样保留。
- `content` 不拼接评测标签、Required Facts、Reference Answer 或模型答案。
- Packet 外层使用 `<context>`；资料文字明确被视为不可信数据，不得覆盖系统规则。
- 排序、去重和字符预算固定；当前受控材料没有触发截断，但脚本会逐题记录截断位置。
- 两阶段第二步只接收第一步输出的 `claim/citation/verbatim_support`，不重新接收原始 Packet。

机器可读的每题 Packet 记录在 `generation_results.jsonl`，其中 `packet_units` 是字段化对象，`packet_allowed_ids` 是当前允许引用集合。
