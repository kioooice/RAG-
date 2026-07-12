# 007 Stronger Generation Model 能力卡

## 目标

在完全不改变 006 Evidence Packet、Oracle Context、Dense Top-5、System Prompt 和 JSON Schema 的前提下，比较 Qwen3-4B-Instruct-2507 Q4_K_M 与唯一获批挑战者 Qwen3.5-9B Q4_K_M。

## 固定边界

- 只运行 `Oracle Packet` 和 `Dense Packet` 单阶段生成；不运行已被 006 否决的 Extract-then-Answer。
- 30 个问题、20 个可回答、10 个不可回答；不新增题目。
- temperature=0、top_p=1、top_k=1、seed=42、max_tokens=256、context=8192。
- llama.cpp b9968、CPU `-ngl 0`；模型仅文本输入，不下载mmproj。
- 4B结果来自006固定记录，9B只消费006已物化的Packet，不重新检索或调参。

## 判定

9B在格式稳定、引用有效和部分事实覆盖上有改善，但Oracle正确率80%仍低于90%，Dense Citation Support为85%低于90%，且页面文件压力很高。因此本轮不把9B设为默认模型；4B保留为低资源对照。
