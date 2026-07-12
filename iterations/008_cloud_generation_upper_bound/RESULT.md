# 008 Cloud Generation Upper Bound：本次执行状态

> 这是一次未完成的受控执行记录，不代表第八轮验收通过。

## 已完成

- `MiMo: Preflight`：通过。
- `MiMo: Smoke Test`：6/6 通过。
- 配置来源：外部 `mimo.ini` 文件；Key 未写入项目、日志或报告。
- 载荷边界检查：通过。
- Smoke 与前 16 个 Formal 请求的 API 响应模型均为 `mimo-v2.5-pro`。
- 已记录 22 次 API 请求，累计按量估算费用约 `0.00627 USD`。

## 未完成

Formal 在第 9 个问题前被本地载荷检查误判并停止。原实现只在全部 Formal 结束后写入结果，因此 16 条已成功的 Formal 响应没有形成可评分结果文件。

当时已使用 22/70 次请求；剩余上限不足以重新执行完整 60 条 Formal 请求。本轮没有继续发送请求，也没有用不完整结果伪造指标。

修复内容已加入执行器：

- 电话/身份证检查改为更窄的格式规则，避免把版面坐标误判为电话；
- Full 运行前检查全部 60 个载荷；
- Formal 结果逐条落盘并支持安全续跑；
- 不再因单条本地检查错误而消耗后续请求。

下一次正式运行需要新的 70 次请求预算或明确的重新授权；当前 `request_manifest.jsonl` 和 `smoke_report.json` 保留作为本次真实执行证据。

## 断点审计（2026-07-12）

- Manifest 尝试数：22；其中 Formal 成功尝试：16。
- Formal 唯一 Query-Condition 组合：16；重复：0。
- `cloud_generation_results.jsonl`：不存在，因此可验证的 Formal 结果数为 **0**，不能把 Manifest 成功尝试当成结果。
- 60/60 Formal 载荷本地预扫描：通过；本次没有发送新请求。
- 续跑器拒绝合并旧记录，原因是历史 Manifest 没有 `request_id` 和输入指纹字段。
- 当前固定输入指纹（仅用于一致性审计，不包含密钥）：
  - dataset：`f0d0c8851006b9fbff6dde94c7bb51aed807502036a751187849d8cc1453d685`
  - prompt：`c65f349d1811b21a6eb1d94db93ef5f75f551e7a8d7f34cb1876775b667d40c4`
  - packet set：`6432891efa7d668c158b667c1efaf066d745fb0ee3fae3804308ada51efeca00`
  - parameters：`442070b01e0f669c3a069e462e7c4d61e72b2bc0b01b1a015ff67ba7fd0ceda3`

由于历史记录缺少可比对的指纹和实际响应结果，不能证明16条 Formal 与当前续跑配置严格一致；按保护规则停止，不重发、不合并、不提高70次上限。
