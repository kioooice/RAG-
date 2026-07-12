# 第七轮结果：Stronger Generation Model

## 1. 做了什么

本轮只比较一个获批挑战者：Qwen3.5-9B Q4_K_M。4B结果直接读取006的固定记录；9B使用相同的30题、相同的Oracle/Dense Context、相同Evidence Packet、相同System Prompt和相同生成参数。

没有运行Extract-then-Answer，没有重新检索、调Prompt、改标签、下载其他模型或加入新组件。

## 2. 烟雾测试

选择了一个单事实题（mxq-001）、一个多事实题（mxq-002）和一个不可回答题（mxq-022），Oracle/Dense各重复3次，共18次：

- 18/18 JSON Schema通过；
- 18/18 Citation ID有效；
- 18/18没有think标签或隐藏推理内容；
- 6组重复结果完全一致；
- 没有乱码、循环生成或截断。

因此进入正式评测。

## 3. 正式指标

| 条件 | 模型 | 可回答正确率 | Required Fact Recall | Citation Validity | Citation Coverage | Citation Support | Unsupported Claim | False Refusal | Schema |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Oracle Packet | 006 Qwen3-4B | 65% | 73.91% | 81.25% | 65% | 65% | 6.67% | 20% | 100% |
| Oracle Packet | Qwen3.5-9B | 80% | 86.96% | 100% | 95% | 95% | 36.67% | 5% | 100% |
| Dense Packet | 006 Qwen3-4B | 80% | 80.43% | 100% | 85% | 85% | 23.33% | 10% | 96.67% |
| Dense Packet | Qwen3.5-9B | 85% | 93.48% | 100% | 85% | 85% | 26.67% | 10% | 100% |

四个正式条件的 `Unanswerable Abstention Rate` 均为 **100%**；9B没有在这组不可回答题上出现错误回答。

9B的主要改善是Oracle引用覆盖、拒答率和部分事实召回；但Unsupported Claim按006固定规则明显上升，通常来自模型将表格事实改写成 `used_facts` 后无法被严格原文支持检查接受。本轮不放宽规则，也不根据结果改Prompt。

## 4. 逐题变化

- Oracle Packet：改善4题、下降1题、不变25题。
- Dense Packet：改善2题、下降1题、不变27题。
- 4B错误而9B正确：6个条件-Query组合。
- 两者都错误：5个条件-Query组合。
- 新增Unsupported Claim：15个条件-Query组合（按固定自动规则统计，需结合逐题原文审查）。
- 新增错误引用：0个；9B正式评测没有出现无效Citation ID。

逐题答案、引用、Packet和变化分类见 [model_comparison.csv](model_comparison.csv) 与 [inspection.html](inspection.html)。

## 5. 验收结论

9B没有通过默认模型验收：

- Oracle正确率80% < 90%；
- Oracle Required Fact Recall 86.96% < 95%；
- Oracle Unsupported Claim 36.67% > 5%；
- Dense Citation Support 85% < 90%。

同时，9B正式评测峰值服务RSS约11.03GB，页面文件峰值约12.87GB，并触发Windows系统管理的页面文件扩展。虽然没有崩溃且完成了全部评测，但这不符合“当前15GB设备无不可接受页面文件压力”的部署要求。

结论：**9B质量有实质改善，但当前硬件部署成本不合格，且可靠生成质量仍未达标，因此不设为默认生成模型。** 保留4B作为低资源对照；下一步只能在更强硬件或经审批的在线模型API之间选择，不自动下载14B/30B，也不开始微调。

## 6. 资源与复现

- 模型下载：5.68GB，SHA-256已在 `MODEL_PROVENANCE.md` 和 `metrics.json` 固定。
- Runtime：沿用llama.cpp b9968；CPU `-ngl 0`；没有mmproj。
- 正式平均总耗时：Oracle约17.81秒/题，Dense约46.83秒/题；Dense P95约62.43秒。
- 生成速度约6–7 tokens/s；完整RSS、GPU和页面文件记录见 `resource_report.json`。

烟雾测试：

```powershell
& 'D:\AI-Lab\envs\retrieval-adaptation-lab-bge-m3\Scripts\python.exe' scripts\run_stronger_generation_model.py --mode smoke `
  --llama-server 'D:\AI-Lab\runtimes\llama.cpp\b9968\llama-server.exe' `
  --model-path 'D:\AI-Lab\models\qwen3.5-9b\unsloth-3885219b6810b007914f3a7950a8d1b469d598a5\Qwen3.5-9B-Q4_K_M.gguf'
```

正式评测使用相同命令，将 `--mode smoke` 改为 `--mode formal`。

## 7. 保护情况

- 001–006所有结果未修改。
- 用户Notebook改动未处理。
- 模型文件、缓存、运行时、服务器日志未进入Git。
