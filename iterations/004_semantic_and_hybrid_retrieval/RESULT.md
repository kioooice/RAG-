# 004 语义与混合检索结果

## 决策

**默认检索方法选择 BGE-M3 Dense。**

Hybrid 不成为默认：在 221 段英文 Corpus 上，它与 Dense 的 Recall@5 完全相同，MRR略低；在中文集上，Hybrid 把 Dense 的 Recall@5 从 1.00 降到 0.70。固定 RRF 把较弱的中文 TF-IDF 排名重新混入，造成明显退化。

TF-IDF 保留为低延迟回退与持续对照，但当前 Corpus 已经证明 Embedding 有必要。

## 固定方法

- A：001 原 TF-IDF配置，不改参数。
- B：`BAAI/bge-m3` Dense，1024维、L2归一化、无Query instruction。
- C：TF-IDF与Dense全量排名用固定 `RRF k=60` 融合。

没有使用 `response`、标签调参、Reranker、BGE稀疏向量、ColBERT或向量数据库。

## 英文正式评测

### 221段Corpus（方法选择依据）

| 方法 | Recall@1 | Recall@3 | Recall@5 | MRR | Top-5未命中 |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0.5606 | 0.8106 | 0.8788 | 0.6952 | 16 |
| BGE-M3 Dense | **0.8106** | **0.9394** | **0.9773** | **0.8807** | **3** |
| 固定RRF Hybrid | 0.7879 | 0.9394 | 0.9773 | 0.8702 | 3 |

Dense 比 TF-IDF 多找回 13 题。Hybrid 没有进一步减少未命中，且首位命中和 MRR 均低于 Dense。

Split 结果：

| 方法 | Split | Recall@5 | MRR | 未命中 |
|---|---|---:|---:|---:|
| TF-IDF | Validation | 0.9091 | 0.6811 | 6 |
| Dense | Validation | 0.9848 | 0.8687 | 1 |
| Hybrid | Validation | 1.0000 | 0.8793 | 0 |
| TF-IDF | Test | 0.8485 | 0.7093 | 10 |
| Dense | Test | 0.9697 | 0.8927 | 2 |
| Hybrid | Test | 0.9545 | 0.8611 | 3 |

### 152段Corpus（与001连续）

| 方法 | Recall@1 | Recall@3 | Recall@5 | MRR | Top-5未命中 |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0.6439 | 0.8712 | 0.9318 | 0.7606 | 9 |
| Dense | 0.8409 | 0.9545 | 0.9848 | 0.8999 | 2 |
| Hybrid | 0.8106 | 0.9621 | 0.9924 | 0.8860 | 1 |

TF-IDF指标与001记录完全一致；运行前同时验证了两个Corpus、132 Query和001指标文件的SHA-256。

## 中文受控评测

- Corpus：29个去重后的真实003 KnowledgeUnit。
- Query：20；关键词10、语义改写10，其中含E02/E03/E07相近代码、相反操作和相近章节名。
- Query与标签分别位于 `chinese_queries.jsonl` 和 `chinese_relevance.jsonl`。

| 方法 | Recall@1 | Recall@3 | Recall@5 | MRR | Top-5未命中 |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0.15 | 0.40 | 0.55 | 0.2742 | 9 |
| Dense | **0.60** | **0.85** | **1.00** | **0.7542** | **0** |
| Hybrid | 0.25 | 0.65 | 0.70 | 0.4542 | 6 |

分类结果：

- 关键词题 Recall@5：TF-IDF 0.40、Dense 1.00、Hybrid 0.60。
- 语义题 Recall@5：TF-IDF 0.70、Dense 1.00、Hybrid 0.80。
- Dense 对型号、故障代码、章节名没有系统性退化；E02、E03近似代码题从TF-IDF的20名以后提升到前1–4名。

中文TF-IDF表现低不代表所有关键词系统都差：29条短KnowledgeUnit包含大量重复概念，中文默认token边界也不理想。这个小集合用于方向验证，不应外推成生产准确率。

## 代表性排名变化

成功改善：

- `emanual_284` “How can I change Antenna type?”：TF-IDF 209 → Dense 1。
- `emanual_451` 音频未通过receiver播放：22 → 1。
- `mxq-004` E03处理：22 → 1。
- `mxq-015` “感知元件掉线后怎样恢复？”：21 → 2。

Dense也不是无条件改善：

- `emanual_473` beautiful screens：TF-IDF 3 → Dense 18，Dense Top-5未命中。
- `emanual_196` beautiful screens：4 → 7。
- 中文“完成维护后还需要留下什么信息？”由3降到4，但仍命中Top-5。

完整逐题变化见 `ranking_changes.csv`，所有Top-5未命中见 `failures.csv`。这些失败在固定评测完成后才查看，没有用于调参。

## 性能与资源代价

221段：

- TF-IDF建库约0.092秒；索引约200KB。
- Dense Embedding约141.4秒；float32向量约905KB。
- TF-IDF平均Query约1.55ms，P95约2.02ms。
- Dense平均Query约251.5ms，P50约257.5ms，P95约289.9ms。
- Hybrid平均Query约255.7ms，且没有质量收益。
- Dense CPU总RSS峰值约2.15GiB；GPU未使用，显存0。

因此默认Dense意味着约160倍的CPU查询延迟和约2GiB常驻内存代价。当前小Corpus可以接受，但上线前应单独验证吞吐、缓存与并发；不能因本轮选择Dense就自动引入向量数据库。

## 停止结论

三种固定方法比较已完成：

- 默认：BGE-M3 Dense。
- 回退/对照：TF-IDF。
- 不采用：当前固定RRF Hybrid。
- 不启动：Reranker、Qdrant、其他Embedding、微调或Query改写。

只有后续真实数据出现Dense Top-5不足、吞吐不可接受或需要大规模持久索引时，才分别提出Reranker、性能优化或向量数据库能力卡。

## 复现

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
D:\AI-Lab\envs\retrieval-adaptation-lab-bge-m3\Scripts\python.exe scripts\evaluate_semantic_hybrid.py `
  --data-dir data\processed\emanual_tfidf `
  --mx100-corpus D:\AI-Lab\data\retrieval-adaptation-lab\retrieval_004\mx100_corpus.jsonl `
  --model-path D:\AI-Lab\models\bge-m3\5617a9f61b028005a4858fdac845db406aefb181 `
  --local-output D:\AI-Lab\data\retrieval-adaptation-lab\retrieval_004\indexes
```
