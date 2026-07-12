# 009 Claim-Level Grounding 结果

## 结论

本轮在API调用前完成了008的完全离线声明审计。旧评测器标记的Unsupported主要是逐字匹配误报，不是MiMo在虚构资料上额外编造产品事实。因此按用户给出的停止条件，不启动新的60条云端复测。

## 做了什么

- 保留008全部结果和指标，只读读取60条Formal回答。
- 将 `used_facts` 和最终回答中的事实拆为117条最小声明。
- 组合检查引用KnowledgeUnit的正文、标题和标题路径。
- 生成了Claim-Level Schema、审计JSONL、修正指标和静态检查页。

## 关键数字

- 60个回答；96条事实声明；21条拒答/说明性文字。
- 008旧规则标记26个回答、63条声明为Unsupported；63条均被审计为 `evaluator_false_positive`。
- Answer-level Unsupported Rate：0%。
- Claim-level Unsupported Rate：0%。
- Material Unsupported Rate：0%。
- Claim Citation Coverage：100%。
- Cited Claim Support：100%。
- Contradicted Claim：0。

## 为什么不继续API评测

Evaluator False Positive占旧标记声明的100%，明显超过20%停止阈值。若现在继续调用，得到的分数仍会被旧口径污染，不能说明Claim-Level协议是否改善模型。因此本轮没有发送请求，也没有修改008模型配置或Prompt。

## 新协议状态

`CLAIM_SCHEMA.md` 定义了 `status + claims[]` 协议，应用层可以按固定顺序连接Claims生成用户答案。该协议目前只完成离线定义和本地检查，尚未经过MiMo API烟雾或Formal验证，不能称为默认云端生成协议。

## 文件

- [claim_audit.jsonl](/D:/Projects/study/retrieval-adaptation-lab/iterations/009_claim_level_grounding/claim_audit.jsonl)
- [metrics_v2.json](/D:/Projects/study/retrieval-adaptation-lab/iterations/009_claim_level_grounding/metrics_v2.json)
- [metrics.json](/D:/Projects/study/retrieval-adaptation-lab/iterations/009_claim_level_grounding/metrics.json)
- [inspection.html](/D:/Projects/study/retrieval-adaptation-lab/iterations/009_claim_level_grounding/inspection.html)
- [audit_claim_grounding.py](/D:/Projects/study/retrieval-adaptation-lab/scripts/audit_claim_grounding.py)

`generation_results.jsonl`只包含“未运行”控制记录，不包含伪造的模型回答；`failures.csv`记录了离线闸门停止原因。

## 下一步

先确认并固定声明级评测口径，再由用户单独批准是否使用预留的 `mimo_009_claim_grounding_v1` 进行API复测。本轮不自动开始下一阶段。
