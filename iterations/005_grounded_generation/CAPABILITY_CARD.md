# 005 Grounded Generation 能力卡

- **能力目标**：在已有 BGE-M3 Dense 检索结果上，用单一、可追溯的本地 Qwen3-4B-Instruct-2507 GGUF 生成有引用的答案，并在证据不足时拒答。
- **输入边界**：002/003 产生的虚构 MX-100 KnowledgeUnit；不使用公司资料、在线搜索或模型生成的标签。
- **固定路径**：`Closed Book`、`Oracle Context`、`Dense RAG` 三种条件；Dense Top-K 固定为 5。
- **输出契约**：`status`、`answer`、`citations`、`used_facts` 四字段 JSON。
- **验收重点**：事实匹配、引用有效性与支持性、拒答率、JSON Schema；LLM-as-a-judge 不参与主要分数。
- **资源边界**：llama.cpp 官方 Windows CPU 预编译包，模型与缓存位于 D 盘；本轮不加入 Reranker、向量库、Agent、联网 API、微调或新模型。
- **停止条件**：完成一个模型的三条件实验并区分检索失败、生成失败和引用失败；不因失败自动更换技术路线。
