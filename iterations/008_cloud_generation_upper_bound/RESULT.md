# 008 Cloud Generation Upper Bound：MiMo-V2.5-Pro

## 结论

新的 `mimo_008_formal_v2` 批次已经完成 60 条可评分 Formal 结果：Oracle 30 条、Dense 30 条。Structured Output、模型名、引用ID和磁盘落盘均通过；但 Oracle 和 Dense 的 `Unsupported Claim Rate` 分别为 36.67% 和 50.00%，因此本轮**未达到可靠资料内生成验收标准**，不把 MiMo 设为已通过的默认生成模型。

本轮只发送完全虚构的 MX-100 Query、Evidence Packet 和固定提示词；没有发送公司资料、文件路径、Notebook、完整Corpus、Key或请求头。

## 两次运行的处理

第一次 Full 在16条 Formal 请求后因本地脱敏规则误判版面数字而停止。那16条响应正文没有保存，已作废，不参与评分，也没有尝试恢复或重新拼接。

第二次使用独立 `run_id=mimo_008_formal_v2` 重新执行全部60条 Formal。历史22次请求和约 `0.00627 USD` 费用保留在总账中；第二次结果单独保存并逐条 flush 后写入新 Manifest。没有重新执行 Smoke。

## 固定配置与一致性

- Model：`mimo-v2.5-pro`
- Base URL：配置文件中的按量付费地址
- Chat Completions：`stream=false`
- Structured Output：MiMo 官方 JSON mode，`response_format={"type":"json_object"}`
- `thinking.type=disabled`
- `temperature=0`，`top_p=1`
- `max_completion_tokens=256`
- 不启用 Web、工具、图片、音频、视频或多轮会话
- 数据集：006-v2 的30个固定问题
- Context：006固定 Oracle Packet 与 Dense Packet

固定输入指纹记录在 `metrics.json`，第二次60条结果全部一致。

## 指标

| 条件 | Answer Correctness | Required Fact Recall | Citation Validity | Citation Support | Unsupported Claim | False Refusal | Unanswerable Abstention | JSON | P50/P95 ms | 成本 USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Oracle Packet | 93.33% | 95.83% | 100% | 100% | 36.67% | 0% | 100% | 100% | 1892 / 4177 | 0.004104 |
| Dense Packet | 90.00% | 91.67% | 100% | 96.67% | 50.00% | 5% | 100% | 100% | 2248 / 4349 | 0.009489 |

累计账目：

- 历史请求：22；第二次 Formal：60；总请求：82/90；
- 新批次重试：0/4；
- 历史费用约 `0.006268 USD`；新批次约 `0.013593 USD`；总计约 `0.019861 USD`；
- 总费用上限：2 USD，未超限；
- Formal 结果：60条，Result-Manifest一一对应，无重复组合。

## 验收判断

Oracle 的正确率、事实召回、引用和拒答率达到阈值，但 Unsupported Claim Rate 超过5%，所以 Oracle 整体不通过。

Dense 的正确率、Oracle差距、引用和拒答率达到部分阈值，但 Required Fact Recall 低于95%，Unsupported Claim Rate 超过5%，所以 Dense 整体不通过。

## 代表性成功

1. `mxq-001`：正确回答 MX-100 温度上限为75℃，引用有效。
2. `mxq-002`：正确回答 E07 为温度过高，并给出停止设备、检查散热。
3. `mxq-019 Oracle`：正确区分 E03 与“检查散热”的冲突条件，回答应断电复位。
4. `mxq-022 Oracle/Dense`：资料不足时返回 `insufficient_evidence`，没有编造蓝牙能力。
5. `mxq-015 Dense`：Dense Packet 中找回 E02 处理方法“检查连接”。

## 代表性失败

1. `mxq-012 Dense`：回答“重启并记录结果”，但未完整覆盖问题要求的事实。
2. `mxq-015 Oracle`：只回答“检查连接”，漏掉要求的其他事实。
3. `mxq-018 Oracle/Dense`：只回答 E02 对应传感器离线，事实不完整。
4. `mxq-019 Dense`：错误拒答，虽然 Dense Context 含有可用于区分 E03 的资料。
5. 多条回答的 `used_facts` 是模型改写或概括，无法逐字在 Context 中验证，因此 Unsupported Claim 率偏高；本轮未为提高分数而调规则。

## 与本地模型比较

第二次批次与固定4B/9B结果逐题比较：

- 46 条组合结果不变；
- MiMo 改善 6 条；
- MiMo 下降 3 条；
- 本地失败、MiMo正确 3 条；
- 三者都失败 2 条。

MiMo 的 Oracle 正确率高于4B和9B，但引用可靠性不能只看 Citation Validity；Unsupported Claim 仍然是主要瓶颈。

## 文件与复现

- [cloud_generation_results.jsonl](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/cloud_generation_results.jsonl)：第二次60条可评分结果；
- [request_manifest_mimo_008_formal_v2.jsonl](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/request_manifest_mimo_008_formal_v2.jsonl)：第二次60条请求记录；
- [metrics.json](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/metrics.json)；
- [model_comparison.csv](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/model_comparison.csv)；
- [failures.csv](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/failures.csv)；
- [inspection.html](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/inspection.html)；
- [CAPABILITY_CARD.md](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/CAPABILITY_CARD.md)、[COMPATIBILITY.md](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/COMPATIBILITY.md)、[DATA_BOUNDARY.md](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/DATA_BOUNDARY.md)；
- [COST_REPORT.md](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/COST_REPORT.md)、[PROVIDER_POLICY_GAPS.md](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/PROVIDER_POLICY_GAPS.md)、[resource_report.json](/D:/Projects/study/retrieval-adaptation-lab/iterations/008_cloud_generation_upper_bound/resource_report.json)。

复现命令：

```powershell
.\.venv\Scripts\python.exe scripts\run_mimo_generation.py --preflight
.\.venv\Scripts\python.exe scripts\run_mimo_generation.py --full --run-id mimo_008_formal_v2
```

第二条命令在已有60条有效结果时只做一致性检查和报告重建，不会重发已完成请求。

本地断点检查结果为 `planned_remaining=0`、`available_remaining=8`、`actual_attempt_count=82`；命令未重发 Smoke 或 Formal。固定输入指纹与 `metrics.json` 一致。

## 边界与后续

本轮仍不是公司资料试运行，也不是供应商采购批准。MiMo 质量已经明显高于旧本地基线的部分指标，但在严格“每个事实都有依据”的规则下仍未通过。下一步只记录为评测规则/失败样本审查；不自动启用 Thinking、不更换模型、不加入其他供应商或工具。
