# Claim-Level 输出协议

009拟采用的模型输出结构如下：

```json
{
  "status": "answered | insufficient_evidence",
  "claims": [
    {
      "text": "一个最小、独立、可验证的事实声明",
      "citations": ["knowledge_unit_id"]
    }
  ]
}
```

## 约束

- 不允许 `answer` 或其他自由文本答案字段。
- `answered` 时每个Claim至少有一个Citation；Citation必须属于当前Context允许的KnowledgeUnit ID。
- `insufficient_evidence` 时 `claims` 必须为空。
- Claim只表达一个事实，不加入未被Evidence明确支持的原因、影响、建议、风险或背景。
- 不向模型提供Reference Answer、Required Facts或评测标签。

## 渲染

应用层按固定顺序连接Claim的 `text` 生成用户可见答案；模型不再进行第二次自由改写。每个Claim的Citation随Claim保留，便于逐条审计。

本协议在本轮只完成离线定义和本地Schema检查，尚未发送009 API请求。
