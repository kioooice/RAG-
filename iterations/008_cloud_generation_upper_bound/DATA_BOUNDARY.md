# 数据边界与脱敏检查

## 允许发送

- `evaluation_dataset_v2.jsonl` 中的完全虚构 MX-100 Query。
- Oracle Evidence Packet 或 Dense Evidence Packet。
- 虚构的 `knowledge_unit_id`、固定系统提示词和 JSON 输出 Schema。

## 禁止发送

- 公司资料、真实人员/部门信息、邮箱、电话或身份证信息。
- 本地文件路径、Git 信息、环境变量、硬件信息和用户 Notebook。
- 完整 Corpus、文件附件、图片、音频、视频、工具调用或在线检索内容。
- `MIMO_API_KEY`、Authorization Header 内容或任何凭据表示。

## 本批次检查

- 60/60 Formal payload 在发送前通过脱敏扫描。
- 结果和报告不包含 API Key 或请求 Header；Manifest 只记录非敏感请求元数据和输入指纹。
- 本轮没有发送公司资料，也没有把 001–007 的其他实验数据作为请求内容。
- 旧 16 条 Formal 正文不再尝试恢复；它们不进入本批次评分。
