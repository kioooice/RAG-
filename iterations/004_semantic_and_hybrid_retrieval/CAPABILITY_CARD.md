# 能力卡：004 Semantic and Hybrid Retrieval

## 用户目标

在不改动 001 TF-IDF 基线的前提下，用固定 Corpus、Query 和标签比较关键词、BGE-M3 Dense 与固定 RRF Hybrid，确定默认检索方法。

## 控制面边界

- 英文输入固定为 152/221 段、132 个 Query、原 Split 和 Relevant Document。
- 不读取 `response`，不改写 Query，不使用标签选模型或调参。
- Dense 固定 `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181`。
- L2 归一化，1024 维，最大长度 8192，无 Query instruction。
- Hybrid 固定 RRF：`score = 1/(60 + lexical_rank) + 1/(60 + dense_rank)`。
- 不做 Reranker、向量数据库、BGE sparse、ColBERT、微调或其他模型比较。

## 验收与决策

- Hybrid 只有满足用户预先声明的全部门槛才可成为默认。
- 若差异很小，保留 TF-IDF。
- 若 Dense 在 221 段至少多找回 2 题、两 Split MRR 不退化、中文精确匹配不退化且语义题至少多找回 2 题，可选择 Dense；Hybrid不得仅因“组合更多技术”而优先。

## 输入与输出

- 英文：001 原始本地 JSONL，运行前校验 SHA-256。
- 中文：003 实际 accepted KnowledgeUnit，37 条经确定性文本去重后为 29 条。
- 中文 Query 与相关性标签分文件人工保存，不使用模型生成答案作为标签。
- 大型模型、缓存、向量和索引只写入 `D:\AI-Lab`，不提交 Git。

## 停止条件

三种固定方法完成英文和中文比较并形成默认结论后立即停止，不因失败样本自动扩展技术范围。
