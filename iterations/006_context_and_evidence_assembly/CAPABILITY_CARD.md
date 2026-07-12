# 006 Context and Evidence Assembly 能力卡

## 能力目标

在不更换 004 Dense 检索器和 005 生成模型的前提下，检查 Oracle Context 的证据完整性，并比较三种固定编排：

1. 005 Dense 单阶段复现；
2. 统一 Evidence Packet 后的单阶段回答；
3. Extract-then-Answer 两阶段回答。

本轮只研究“上下文怎样交给生成模型”和“证据怎样被标准化组装”。不包含新检索方法、切块调参、Reranker、向量数据库、微调或新模型。

## 固定边界

- 模型：Qwen/Qwen3-4B-Instruct-2507，固定 Round 5 GGUF SHA-256。
- 检索：BAAI/bge-m3 Dense，Top-K=5，使用 005 相同 29 个 KnowledgeUnit。
- 生成：temperature=0，top_p=1，top_k=1，seed=42，reasoning off，max_tokens=256。
- 评测：002/003 的虚构 MX-100 资料和 005 的 20 个可回答、10 个不可回答问题。
- `iterations/005_grounded_generation/` 只读；v2 只增加审计元数据，不改原始标签。

## 验收解释

先用 `ORACLE_AUDIT.md` 确认 Required Facts 确实在 Oracle Context 中。若 Oracle Evidence Completeness 不是 100%，不能把 Oracle 失败直接解释为生成能力；本轮若为 100%，再比较 Context 格式和两阶段证据抽取造成的变化。

## 停止条件

完成审计、Evidence Packet 单阶段和 Extract-then-Answer 后停止。若完整 Oracle 仍达不到门槛，只记录“4B 量化模型不足”的证据，不自动下载更强模型。
