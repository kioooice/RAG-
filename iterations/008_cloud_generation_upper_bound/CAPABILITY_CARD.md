# 008 云端资料内生成能力卡

## 能力目标

在完全虚构的 MX-100 资料上，验证 MiMo-V2.5-Pro 是否能在固定 Evidence Packet 内回答问题、给出有效引用，并在资料不足时拒答。此次是云端质量上限实验，不是公司资料试运行或供应商采购批准。

## 固定输入与方法

- 模型：`mimo-v2.5-pro`，OpenAI-compatible Chat Completions。
- 条件：Oracle Packet 与 Dense Packet，各 30 题；总计 60 条 Formal。
- 输入：006-v2 的固定 Query、Evidence Packet、系统提示词和 JSON Schema。
- 配置：`thinking.type=disabled`、`stream=false`、`temperature=0`、`top_p=1`、`max_completion_tokens=256`、JSON mode。
- 数据边界：只发送虚构 Query、Evidence Packet 和虚构 KnowledgeUnit ID；不发送公司资料、完整Corpus、文件或环境信息。
- Token Plan 检查仍保留；本批次使用普通按量付费 Base URL，不混用 Token Plan 地址。

## 结果判定

新批次 `mimo_008_formal_v2` 的 60 条结果均已保存并可评分。Oracle 的正确率和事实召回达到阈值，但 Unsupported Claim Rate 为 36.67%；Dense 的事实召回为 91.67%，Unsupported Claim Rate 为 50.00%。因此两种条件均未通过完整可靠资料内生成验收标准，MiMo 暂不设为默认生成模型。

## 明确不包括

- 不比较其他云端模型，不启用 Thinking、工具、Web、Agent 或多轮会话。
- 不修改检索器、Prompt、评测标签或 Evidence Packet。
- 不把虚构数据上的通过结果外推为可处理真实公司资料。
