# 第六轮结果：Context and Evidence Assembly

## 1. 本轮做了什么

本轮只审计证据覆盖并比较上下文组装方式，没有更换 BGE-M3、Qwen3-4B、GGUF、llama.cpp、Top-K 或生成参数，也没有修改 005 文件。

- 从 003 的实际 KnowledgeUnit 导出 29 个去重单元，文本与 004 使用的 29 个单元逐条一致。
- 审计 005 的 20 个可回答问题：46 个 Required Facts 在 Oracle Context 中全部找到，Oracle Evidence Completeness **100%（46/46）**；Dense Top-5 的 Context Required Fact Coverage 也是 **100%**。
- 建立 `evaluation_dataset_v2.jsonl`。它保留原 Query、Relevant Unit、Required Facts 和 Reference Answer，只增加确定性的来源位置和标签保留说明；`LABEL_CHANGELOG.md` 记录了没有改 Ground Truth。
- 对每题构造 Evidence Packet，保存 `knowledge_unit_id`、`document_id`、标题路径、来源定位、类型和原文；本实验没有触发截断，重复文本只保留首次出现的单元。

## 2. 固定实验

| 条件 | Context | 生成编排 |
|---|---|---|
| `baseline_dense` | 005 原来的 `[unit_id] text` Dense Top-5 | 005 单阶段 JSON（复现） |
| `oracle_packet` | 人工标注 Oracle Unit 的 Evidence Packet | Packet 单阶段 |
| `dense_packet` | 相同 Dense Top-5 的 Evidence Packet | Packet 单阶段 |
| `oracle_extract` | Oracle Packet | 先抽取 `claim/citation/verbatim_support`，再回答 |
| `dense_extract` | Dense Packet | 先抽取，再只根据抽取结果回答 |

所有请求都使用 temperature=0、top_p=1、top_k=1、seed=42、max_tokens=256、reasoning off。评测集仍是 20 个可回答问题和 10 个不可回答问题；模型没有看到 Required Facts、Reference Answer 或评测标签。

## 3. 主要指标

百分比是 30 题总体中的确定性规则统计；`Required Fact Recall` 只在 20 个可回答题的 46 个事实中计算。

| 条件 | 可回答正确率 | Required Fact Recall | Unsupported Claim | Citation Validity（已回答） | Citation Coverage（全部可回答） | False Refusal | JSON Schema |
|---|---:|---:|---:|---:|---:|---:|---:|
| 005 Dense 原记录 | 70.0% | 86.96% | 40.0% | 100% | 80.0% | 20.0% | 100% |
| 本轮 Dense 单阶段复现 | 70.0% | 86.96% | 10.0% | 100% | 80.0% | 20.0% | 100% |
| Oracle Packet 单阶段 | 65.0% | 73.91% | 6.67% | 81.25% | 65.0% | 20.0% | 100% |
| Dense Packet 单阶段 | 80.0% | 80.43% | 23.33% | 100% | 85.0% | 10.0% | 96.67% |
| Oracle Extract-then-Answer | 25.0% | 43.48% | 0% | 100% | 45.0% | 55.0% | 33.33% |
| Dense Extract-then-Answer | 20.0% | 47.83% | 0% | 100% | 55.0% | 45.0% | 40.0% |

“Citation Validity”同时另存了两阶段引用是否属于第一阶段选中集合；`metrics.json` 中 `citation_validity_selected_answered` 为 100%，但这不抵消 Citation Coverage 只有 45%/55% 的事实覆盖不足。

### 基线复现

本轮重新调用相同本地模型完成 30 个 Dense 单阶段请求：

- 26/30 个输出逐字段完全一致；
- 29/30 个 Query 的 status 和 answer 一致；
- 4 个差异为部分引用集合或标点/空白差异（`mxq-009`、`mxq-010`、`mxq-020`、`mxq-028`），没有改变 Dense Top-5，且整体正确率、Required Fact Recall、Citation Coverage 和 False Refusal 与 005 一致。

这说明当前 CPU llama.cpp 运行的逐字输出并非完全稳定；后续比较应优先使用保存的指标和事实规则，不把非实质性标点差异当作检索变化。

### Extract 阶段

- 第一阶段 JSON Schema 通过率：**96.67%**；Oracle 为 100%，Dense 为 93.33%。
- Evidence Extraction Precision：**84.58%**；Recall：**78.06%**。
- 只看 20 个可回答题时，Precision 为 **76.88%**、Recall 为 **67.08%**；总体数值包含 10 个“应为空证据”的不可回答题，不能把空抽取误读成资料覆盖能力。
- 有效 `verbatim_support` 条目占全部抽取条目的 **87.76%**。无效条目在 `generation_results.jsonl` 中逐条保留，未被静默修正。
- 两阶段会增加一次模型调用；每题分别保存第一阶段、第二阶段和总额外延迟。平均单阶段总耗时约 3.85 秒（Oracle Extract 最终调用平均值）和 4.17 秒（Dense Extract 最终调用平均值），完整两阶段还要加上第一阶段耗时。

## 4. 失败来源解释

由于 Oracle 和 Dense 的 Required Facts 覆盖均为 100%，本轮没有 `context_missing` 或 `label_incomplete`。主要失败是：

- **模型遗漏 / 错误拒答**：Oracle Packet 仍有 7 个事实遗漏、4 个可回答题拒答；Extract 的第一阶段或第二阶段进一步丢失事实。
- **引用错误**：Packet 单阶段出现无效或未覆盖事实的引用；Extract 的引用 ID 本身多为有效，但 Citation Coverage 仍不足。
- **Schema 错误**：Dense Packet 1 题；Oracle/Dense Extract 的最终回答分别有 20/18 题不符合三字段最终 Schema，通常是模型输出了额外字段、解释或截断。
- **冲突事实观察**：`failure_types.conflict_fact` 只在 `answered` 回答中统计正向冲突断言。不可回答题在“资料未提及……”的拒答句中复述问题词会保留在原始回答，但不会被误报为冲突事实。

005 的 Unsupported Claim=40% 原始值原样保存在 `metrics.json.round5_reference_metrics`；本轮重算时把拒答中的问题词排除，并逐条检查 `used_facts` 是否能由 Packet 支持，所以本轮复现值不是对 005 文件的覆盖或改写。

具体题目的 Oracle Unit、Dense Top-5、Required Fact 位置、Packet、抽取结果和最终回答可在 `inspection.html` 逐题查看。

## 5. 结论

本轮**没有达到**把 Extract-then-Answer 设为默认编排的门槛：完整 Oracle 下正确率 25%、Required Fact Recall 43.48%、False Refusal 55%，远低于 90%/95%/10%。Evidence Packet 单阶段也没有达到门槛，且 Oracle Packet 比 005 Oracle 单阶段更差；Dense Packet 的 80% 正确率是一个局部改善，但不能掩盖引用覆盖和 Schema 失败。

因此形成的证据是：**在 Oracle Evidence Completeness 已经达到 100% 的条件下，当前 Qwen3-4B Q4_K_M 量化模型仍不足以承担可靠的资料内生成，尤其不适合直接采用两阶段抽取编排。** 本轮不下载更强模型、不修改检索器，下一轮只能在明确批准后比较更强生成模型。

## 6. 复现命令

先生成/审计 v2（不触碰 005）：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_context_assembly.py `
  --iteration-dir iterations\006_context_and_evidence_assembly `
  --dataset-005 iterations\005_grounded_generation\evaluation_dataset.jsonl `
  --generation-005 iterations\005_grounded_generation\generation_results.jsonl `
  --evidence-units iterations\006_context_and_evidence_assembly\evidence_units.jsonl
```

在已有 BGE 环境、D 盘模型和本地 llama.cpp 下运行固定实验：

```powershell
& 'D:\AI-Lab\envs\retrieval-adaptation-lab-bge-m3\Scripts\python.exe' scripts\run_context_assembly.py `
  --bge-model-path 'D:\AI-Lab\models\bge-m3\5617a9f61b028005a4858fdac845db406aefb181' `
  --llama-server 'D:\AI-Lab\runtimes\llama.cpp\b9968\llama-server.exe' `
  --model-path 'D:\AI-Lab\models\qwen3-4b-instruct-2507\unsloth-a06e946bb6b655725eafa393f4a9745d460374c9\Qwen3-4B-Instruct-2507-Q4_K_M.gguf' `
  --runtime-dir 'D:\AI-Lab\envs\retrieval-adaptation-lab-llama-cpp-round6' --port 18081
```

报告重算（不再次调用模型）：

```powershell
& 'D:\AI-Lab\envs\retrieval-adaptation-lab-bge-m3\Scripts\python.exe' scripts\finalize_context_assembly.py `
  --iteration-dir iterations\006_context_and_evidence_assembly `
  --dataset-v2 iterations\006_context_and_evidence_assembly\evaluation_dataset_v2.jsonl `
  --dataset-005 iterations\005_grounded_generation\evaluation_dataset.jsonl `
  --metrics-005 iterations\005_grounded_generation\metrics.json `
  --evidence-units iterations\006_context_and_evidence_assembly\evidence_units.jsonl
```

## 7. 边界与保护

- 本轮资料仍是 002/003 生成的虚构 MX-100 KnowledgeUnit，不是原始 PDF/OCR/切块能力验证。
- 没有提交模型、缓存、llama.cpp runtime、服务器日志或大文件；生成 JSONL/HTML 是本轮小规模评测记录。
- 001–005 结果、Notebook 改动和原始 005 评测集保持不变。
