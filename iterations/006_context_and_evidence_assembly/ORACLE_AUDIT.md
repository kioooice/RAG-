# Oracle Context 审计

005 原始评测集保持不变；本轮只读取它并生成 `evaluation_dataset_v2.jsonl`。审计依据是实际 003 Docling KnowledgeUnit 元数据和 005 Dense Top-5 记录，不使用模型答案修改标签。

- 005 dataset SHA-256：`a61a515ebe6604c88293685519563a888c7b816cc8baa8b28922aa237af79555`
- 可回答题：20；Required Fact 总数：46
- Oracle Evidence Completeness：**100.00%**（46/46）
- Dense Evidence Completeness：**100.00%**（46/46）
- 所有20题的原Oracle Unit均覆盖全部Required Facts，因此没有把生成失败归因于标签不完整或Context缺少事实。

## 逐题审计

| Query | Oracle覆盖 | Oracle Unit | Dense补充Unit | Dense缺失事实 | 005观察分类 |
|---|---:|---|---|---|---|
| mxq-001 | 100% | unit_427bb9da85d5c2c78e94 | unit_ea417ff8aa45e3b8d3ea, unit_b85a502fbfddf27ee43b, unit_4f021d52061a98f6ac53, unit_d2026ce4866fbfe12c00 | 无 | none |
| mxq-002 | 100% | unit_94850904cf039fcc1678 | unit_5ea191c13e5954131884, unit_088a259df618945202b2, unit_4e6240ee45aff210b43d, unit_8b8c7f0d85cd4c16345f | 无 | none |
| mxq-003 | 100% | unit_94850904cf039fcc1678 | unit_931b71f8106f5858e816, unit_d2ea24bd55aa60e58786, unit_4e6240ee45aff210b43d, unit_8b8c7f0d85cd4c16345f | 无 | none |
| mxq-004 | 100% | unit_94850904cf039fcc1678 | unit_5ea191c13e5954131884, unit_931b71f8106f5858e816, unit_4e6240ee45aff210b43d, unit_8b8c7f0d85cd4c16345f | 无 | none |
| mxq-005 | 100% | unit_03db816ac89ed1434516 | unit_12f442be965b3ab2a53c, unit_9bb8855a2a4f363809a2, unit_b85a502fbfddf27ee43b, unit_bf63107d404eac25b0fa, unit_d2026ce4866fbfe12c00 | 无 | citation_error |
| mxq-006 | 100% | unit_03db816ac89ed1434516 | unit_766c48cf1448479c2315, unit_4912a65c603f231bd224, unit_2bd1304003c7f0dfea98, unit_0163e2051a2ebd5d095e, unit_5a011d6f4cc5f7bf21e8 | 无 | none |
| mxq-007 | 100% | unit_0163e2051a2ebd5d095e | unit_2bd1304003c7f0dfea98, unit_766c48cf1448479c2315, unit_12f442be965b3ab2a53c, unit_b85a502fbfddf27ee43b | 无 | false_refusal |
| mxq-008 | 100% | unit_4102e7b75c61bddf397f | unit_0163e2051a2ebd5d095e, unit_088a259df618945202b2, unit_12dd3556798a53065a50, unit_4f021d52061a98f6ac53 | 无 | false_refusal |
| mxq-009 | 100% | unit_0cadd16eefbcfde43d0b | unit_5a011d6f4cc5f7bf21e8, unit_5ea191c13e5954131884, unit_52f7d2948d68aee317d1, unit_4e6240ee45aff210b43d | 无 | none |
| mxq-010 | 100% | unit_94850904cf039fcc1678 | unit_0cadd16eefbcfde43d0b, unit_4e6240ee45aff210b43d, unit_8b8c7f0d85cd4c16345f, unit_d2ea24bd55aa60e58786 | 无 | none |
| mxq-011 | 100% | unit_0861be8afba46dca2c51 | unit_0163e2051a2ebd5d095e, unit_1d7396a1c70ac608332a, unit_bf63107d404eac25b0fa, unit_2bd1304003c7f0dfea98 | 无 | none |
| mxq-012 | 100% | unit_0861be8afba46dca2c51 | unit_967fd3b16072f006b613, unit_1d7396a1c70ac608332a, unit_0163e2051a2ebd5d095e, unit_5a011d6f4cc5f7bf21e8 | 无 | model_omission |
| mxq-013 | 100% | unit_0861be8afba46dca2c51 | unit_0163e2051a2ebd5d095e, unit_2bd1304003c7f0dfea98, unit_766c48cf1448479c2315, unit_4912a65c603f231bd224 | 无 | none |
| mxq-014 | 100% | unit_088a259df618945202b2 | unit_5ea191c13e5954131884, unit_5a011d6f4cc5f7bf21e8, unit_ea417ff8aa45e3b8d3ea, unit_0cadd16eefbcfde43d0b | 无 | none |
| mxq-015 | 100% | unit_94850904cf039fcc1678 | unit_2bc981741b7b9f68f243, unit_931b71f8106f5858e816, unit_4912a65c603f231bd224, unit_d2ea24bd55aa60e58786 | 无 | model_omission |
| mxq-016 | 100% | unit_94850904cf039fcc1678 | unit_2bc981741b7b9f68f243, unit_4912a65c603f231bd224, unit_0163e2051a2ebd5d095e, unit_0861be8afba46dca2c51 | 无 | model_omission |
| mxq-017 | 100% | unit_0861be8afba46dca2c51 | unit_2bc981741b7b9f68f243, unit_0163e2051a2ebd5d095e, unit_4912a65c603f231bd224, unit_1d7396a1c70ac608332a | 无 | none |
| mxq-018 | 100% | unit_94850904cf039fcc1678 | unit_931b71f8106f5858e816, unit_d2ea24bd55aa60e58786, unit_4e6240ee45aff210b43d, unit_8b8c7f0d85cd4c16345f | 无 | model_omission |
| mxq-019 | 100% | unit_94850904cf039fcc1678 | unit_4e6240ee45aff210b43d, unit_8b8c7f0d85cd4c16345f, unit_d2ea24bd55aa60e58786, unit_931b71f8106f5858e816 | 无 | false_refusal |
| mxq-020 | 100% | unit_0163e2051a2ebd5d095e | unit_2bd1304003c7f0dfea98, unit_766c48cf1448479c2315, unit_0861be8afba46dca2c51, unit_12f442be965b3ab2a53c | 无 | false_refusal |

## 005 Oracle 失败类型

| 类型 | 数量 | 定义 |
|---|---:|---|
| label_incomplete / context_missing | 0 | Oracle Unit 中没有 Required Fact |
| model_omission | 4 | Context完整，但答案漏掉事实 |
| false_refusal | 4 | Context完整，却返回 insufficient_evidence |
| citation_error | 1 | 引用ID不存在或不在允许集合 |
| conflict_fact | 0 | 答案包含冲突事实 |
| schema_error | 0 | 输出不满足固定Schema |

结论：Oracle Evidence Completeness 达到100%，因此第六轮可以把差异解释为Context格式和生成编排问题，而不是原始标签缺失。

## 005 中 Dense 与 Oracle 的差异线索

以下只是读取 005 已有结果，不是本轮调参：

- Dense 优于 Oracle：`mxq-012`（滤网后续步骤）、`mxq-018`（E02/E07 传感器离线辨别）、`mxq-020`（维护章节定位）。
- Oracle 优于 Dense：`mxq-004`（E03 处理）。

这些题的 Required Facts 在 Oracle 中均完整；Dense 的补充 Unit 可能提供了更适合生成模型组织答案的相邻表格或标题，但这不能证明 Dense Context 本身包含更多人工标注事实。第六轮用 Packet 和两阶段实验进一步区分这种上下文组织差异与生成差异。
