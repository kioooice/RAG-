# 005 Grounded Generation 结果

## 结论先说

本轮已经完成一个本地 Qwen3-4B-Instruct-2507 Q4_K_M 模型的三条件实验，但没有达到进入下一阶段的验收线。最关键的结果是：Oracle Context 的可回答题正确率只有 **60%（12/20）**，因此按照预先约定的停止条件，不更换模型、不调检索器、不加入 Reranker 或向量数据库。Dense RAG 的失败主要是生成层失败，而不是本轮 Dense Top-5 没有提供相关资料。

本轮没有修改 001—004 的结果，也没有处理两个用户 Notebook。

## 做了什么

- 使用固定的 BAAI/bge-m3 Dense Top-5 作为 Dense RAG 条件。
- 使用同一个固定 system prompt、JSON 输出契约、`temperature=0`、`top_k=1`、`seed=42`、最大 256 token 和 `reasoning=off`，分别运行 Closed Book、Oracle Context、Dense RAG。
- 本地运行时是 llama.cpp `b9968`，模型是可追溯的第三方 `unsloth/Qwen3-4B-Instruct-2507-GGUF` Q4_K_M 文件；模型文件哈希已在 `COMPATIBILITY.md` 和 `resource_report.json` 中锁定。
- 评测集是 20 个资料内问题和 10 个资料不足问题，来源仅为 002/003 的虚构 MX-100 KnowledgeUnit 与 004 中文评测基础。每题的 reference answer、required facts、冲突事实和可接受引用均为人工定义，不使用模型生成答案作标签。

## 数据规模和映射

Corpus 为 002/003 已产生的 29 个 MX-100 KnowledgeUnit。Oracle 只放评测集中的人工相关单元；Dense RAG 使用同一 Corpus 的 Dense Top-5；Closed Book 的 Context 为空。Dense 的“检索失败”判定同时考虑人工 ID 和文本中是否出现要求事实，以免把内容相同的重复段落误报为检索失败。

数据文件：`evaluation_dataset.jsonl`；完整生成记录：`generation_results.jsonl`；机器指标：`metrics.json`。

## 复现命令

```powershell
$env:HF_HOME='D:\AI-Lab\cache\huggingface'
$env:HF_HUB_CACHE='D:\AI-Lab\cache\huggingface\hub'
$env:HF_DATASETS_CACHE='D:\AI-Lab\cache\huggingface\datasets'
$env:TRANSFORMERS_OFFLINE='1'
$env:HF_HUB_OFFLINE='1'
& 'D:\AI-Lab\envs\retrieval-adaptation-lab-bge-m3\Scripts\python.exe' scripts\run_grounded_generation.py `
  --mx100-corpus 'D:\AI-Lab\data\retrieval-adaptation-lab\retrieval_004\mx100_corpus.jsonl' `
  --bge-model-path 'D:\AI-Lab\models\bge-m3\5617a9f61b028005a4858fdac845db406aefb181' `
  --llama-server 'D:\AI-Lab\runtimes\llama.cpp\b9968\llama-server.exe' `
  --model-path 'D:\AI-Lab\models\qwen3-4b-instruct-2507\unsloth-a06e946bb6b655725eafa393f4a9745d460374c9\Qwen3-4B-Instruct-2507-Q4_K_M.gguf' `
  --runtime-dir 'D:\AI-Lab\envs\retrieval-adaptation-lab-llama-cpp'
```

项目内的静态检查页：`iterations/005_grounded_generation/inspection.html`。

## 指标

| 条件 | 可回答正确率 | Required Fact Recall | Unsupported Claim Rate | Citation Validity | Citation Support Rate | 不可回答拒答率 | 错误来源 | 平均总耗时 | 平均首 Token | 平均输出 / 速度 |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Closed Book | 0% (0/20) | 23.91% | 53.33% | 100% | 0% | 100% (10/10) | 20 生成失败 | 3294 ms | 963 ms | 35.7 tok / 15.14 tok/s |
| Oracle Context | 60% (12/20) | 82.61% | 26.67% | 96.67% | 75% | 100% (10/10) | 8 生成失败、1 引用失败 | 4536 ms | 1137 ms | 51.3 tok / 14.94 tok/s |
| Dense RAG | 70% (14/20) | 86.96% | 40.00% | 100% | 80% | 100% (10/10) | 6 生成失败、0 检索失败 | 9580 ms | 4282 ms | 75.6 tok / 14.37 tok/s |

`metrics.json` 同时保存 P50/P95、输入/输出 token、JSON Schema 通过率、拒答率、False Refusal Rate 和资源信息。Dense 的 False Refusal Rate 为 20%（4/20）；Oracle 也是 20%（4/20）。

### 验收判断

- Oracle 可回答正确率 60% < 90%，未通过。
- Oracle Citation Validity 96.67% < 100%，未通过；有一个模型生成的 citation ID 不存在于 Context。
- Oracle Citation Support Rate 75% < 95%，未通过。
- Oracle Unsupported Claim Rate 26.67% > 5%，未通过。
- Oracle 不可回答拒答率 100%，通过这一项。
- Dense 没有文本证据层面的检索失败，但生成正确率和引用支持仍未接近可接受生产门槛。

## 典型成功样本

以下是人工规则确认正确、且引用支持要求事实的例子：

1. `mxq-001`：回答“MX-100的温度上限是75℃”，引用 `unit_427bb9da85d5c2c78e94`。
2. `mxq-002`：回答 E07 是温度过高，应停止设备并检查散热，引用 `unit_94850904cf039fcc1678`。
3. `mxq-003`：回答 E02 是传感器离线并检查连接，引用 `unit_94850904cf039fcc1678`。
4. `mxq-010`：把高温告警定位到散热检查，引用 `unit_94850904cf039fcc1678`。
5. `mxq-017`：识别维护顺序先断电，再进行后续维护，Dense 还返回了完整三步，引用 `unit_0861be8afba46dca2c51` 等。

10 个不可回答问题在三种条件下都达到 100% 拒答率，没有因为 E07/E02/E03 等相似内容而编造 E09、电压、功耗、蓝牙或保修信息。

## 典型失败样本和错误归因

1. `mxq-007` / `mxq-008`：Oracle 已给出只有章节标题的正确单元，模型仍返回“资料中未提及”，属于生成层的 False Refusal，不是检索失败。
2. `mxq-012`：问题要求“清洁滤网之后”的下一步，模型只回答“重启并记录结果”，漏掉了顺序上下文中的部分要求事实，属于生成失败。
3. `mxq-015`：模型只回答“检查连接”，漏掉 E02 和“传感器离线”的完整关联，属于 Required Fact Recall 不足。
4. `mxq-018`：模型回答 E02 是传感器离线，但没有同时说明 E07 的对照含义，难负例上的事实覆盖不完整。
5. `mxq-005`：答案中的版本事实正确，但模型输出了不存在的 `unit_03db816ac89ed14348516`，实际 Context ID 是 `unit_03db816ac89ed1434516`，因此是引用失败。
6. `mxq-019`：资料足以支持“E03 不应检查散热、应断电复位”，模型却用 `insufficient_evidence` 拒答，属于生成失败。

这些观察均由问题、Context、人工标签和实际 JSON 直接得到；没有让模型自动解释失败原因。

## 当前模型擅长什么

- 对短小、直接复述资料的型号、温度、故障代码和简单处理步骤，能够生成合法 JSON 并给出有效引用。
- 对资料不足问题的保守拒答表现很好：本轮 10/10 正确拒答。
- 在 Dense Context 中可以利用重复或同义 KnowledgeUnit；本轮 Dense 没有被判为文本证据缺失的检索失败。

## 当前模型不擅长什么

- 章节标题、操作顺序和需要同时比较两个故障代码的问题，容易过度拒答或只返回部分事实。
- 不能稳定把每个关键事实映射到正确 citation；事实正确不等于引用正确。
- Context 变长后平均总耗时约 9.6 秒，CPU 峰值约 7.98 GB（模型服务进程），不适合作为未经进一步工程化的交互默认配置。

## 已知限制

- 这是 29 个虚构 KnowledgeUnit 的小型中文评测，不代表真实设备资料或广泛中文能力。
- “Unsupported Claim Rate”使用固定字符串/短语与 Context 的确定性规则，不是完整自然语言事实证明器。
- 首 Token 延迟由 llama.cpp 返回的 prompt 时间加首个预测 token 的平均时间得到；不是网络服务端到端流式采样的独立硬件计时。
- 使用第三方 GGUF。它的 card、官方基座链接、提交和文件 SHA-256 可复核，但发布者没有提供基座 commit 与转换命令的机器可验证绑定，详见 `COMPATIBILITY.md`。
- 本轮用 CPU 后端运行；RTX 4050 只做设备识别和资源观察，没有将 CUDA/Vulkan 性能混入指标。

## 下一步建议（不自动开始）

下一步最值得验证的单一假设是：**在不改变模型和检索器的情况下，把固定 Context 组装成更短、更明确的“事实—来源”条目，能否减少章节标题和顺序问题的 False Refusal，同时保持不可回答题的拒答率。** 这应作为后续独立实验；本轮不修改 Prompt、不加入 Reranker、不更换模型。
