# 001：TF-IDF 证据检索基线结果

## 1. 做了什么

从固定版本的公开 RAGBench `emanual` 中以 streaming 读取 `validation + test`，把重复 Query 的两条上下文记录合并，构造 132 个唯一 Query 与 152 个唯一文档的共享语料。实现了固定配置的词级 TF-IDF 检索器、Top-K 排序、指标计算、失败样本导出和命令行查询入口；没有使用答案文本、大模型、Embedding 或向量数据库。

本轮输入是数据集已经抽取或整理好的文本型 `documents`。没有原始 PDF 解析、OCR、版面恢复、清洗、切块设计或元数据构建，因此本轮既不是“已经完成资料建库”，也不是“完整 RAG”；它只验证了给定文本单元上的证据检索能力。

## 2. 使用的真实字段

- Query：`question`
- 候选文档：`documents`
- Relevant Document：`all_relevant_sentence_keys` 的数字前缀映射到 `documents` 下标
- Reference Answer：`response`；同 Query 的多个答案全部保存在 `reference_answers`，但不参与检索
- 原始 Query ID：`id`

`documents` 是每个 Query 预先提供的文本列表，对本实验而言已经是可索引的文档/段落单元。数据还提供 `documents_sentences`，但没有提供原始 PDF、页面坐标或完整切块过程，因此不能据此断言官方最初如何切块。本轮没有实现或评价前处理。

数据集、字段和异常处理的完整说明见 `data_profile.md`。

## 3. 数据规模

- 数据集：`galileo-ai/ragbench`
- 版本：`97808f3e5fd16ede40bbff6c2949af8139b2eb7b`
- 配置 / Split：`emanual` / `validation + test`
- 源记录：264 行
- 合并的重复 Query 记录：132 行
- 最终唯一 Query：132
- 候选文档出现次数：792
- 确定性去重后的 Corpus：152 个文档
- 平均文档长度：137.91 个空白分隔词，816.93 个字符
- 缺少相关键的源记录：1；同 Query 的另一条记录提供了有效映射，最终 0 个 Query 缺少 Relevant Document

## 4. 运行命令

```powershell
$env:HF_HOME='D:\AI-Lab\cache\huggingface'
$env:HF_HUB_CACHE='D:\AI-Lab\cache\huggingface\hub'
$env:HF_DATASETS_CACHE='D:\AI-Lab\cache\huggingface\datasets'
$env:TORCH_HOME='D:\AI-Lab\cache\torch'
$env:PIP_CACHE_DIR='D:\AI-Lab\cache\pip'

.\.venv\Scripts\python.exe scripts\prepare_emanual.py --query-count 132 --seed 20260711
.\.venv\Scripts\python.exe scripts\evaluate_tfidf.py
.\.venv\Scripts\python.exe -m unittest tests.test_retrieval_metrics -v
.\.venv\Scripts\python.exe scripts\query_tfidf.py "How can I change the TV name?"
```

## 5. 指标

指标中的 Recall@K 表示每个 Query 的前 K 项是否命中任意一个相关文档，再对 Query 求平均；多相关文档不重复加权。MRR 使用第一个相关文档的倒数排名。

| 指标 | 结果 |
| --- | ---: |
| Recall@1 | 0.6439 |
| Recall@3 | 0.8712 |
| Recall@5 | 0.9318 |
| MRR | 0.7606 |
| Recall@5 未命中 | 9 / 132 |
| 平均单次查询耗时 | 约 0.71 ms |

耗时只反映本机、152 文档内存索引上的本次运行，不应外推到大型知识库。精确机器可读值见 `metrics.json`。

## 6. 五个成功样本

1. `emanual_363`：问题询问能否修改网络中的 TV 名称；Top-1 直接命中标题为 “Changing the name of the TV on a network” 的相关文档，分数约 0.6686。
2. `emanual_359`：问题询问能否用移动设备打开 TV；Top-1 命中 “Turning on the TV with a mobile device”，分数约 0.5730。
3. `emanual_64`：问题询问如何自动启动上次使用的应用；Top-1 命中 “Launching the last used app automatically”，分数约 0.5033。
4. `emanual_507`：问题询问如何调整 HDMI black level；Top-1 命中 “Using HDMI black level”，分数约 0.4827。
5. `emanual_26`：问题询问 sleep timer 和 off timer；Top-1 命中 “Using the timers”，分数约 0.4732。

这些例子共同特点是 Query 与正确文档在标题、功能名或菜单术语上有直接词面重合。

## 7. 五个失败样本

1. `emanual_325`：询问如何只查看 favorite list 中的频道；Top-1 是“从收藏列表移除频道”，共享 favorite/channels/list 词项，但不是标注相关文档。
2. `emanual_282`：询问从哪里查看 program information；Top-1 是 “Using the guide”，语义接近且关键词更多，但标注相关文档未进入 Top-5。
3. `emanual_284`：询问如何更改 Antenna type；Top-1 是应用故障文档，其中出现了 change 等泛化词，正确文档与 Query 没有足够共享词项。
4. `emanual_1`：问题含拼写错误 “serch”，询问 source 与频道数据；Top-1 错误命中 Smart Hub 文档，正确文档未进入 Top-5。
5. `emanual_489`：短问题 “Can I configure Color?”；Top-1 错误命中 input signal 文档，短 Query 提供的区分词太少。

逐条可观察信息见 `failures.csv`。实际 Recall@5 未命中只有 9 条，因此文件还按规则补充了 11 条低排名或低分命中，共 20 条。

## 8. TF-IDF 擅长什么

- 菜单项、功能名、设备术语与文档标题直接重合的查询。
- 在小型共享语料中快速给出可解释的分数与排序。
- 不依赖模型下载，结果容易复现，适合作为后续方法的最低对照线。

## 9. TF-IDF 不擅长什么

- Query 与文档使用不同说法、同义词或描述方式。
- 拼写错误、极短 Query 和只含泛化词的 Query。
- 多篇文档共享相同功能词时区分真正相关段落。
- 长文档中少量相关词项被大量无关词稀释的情况。

## 10. 是否足以进入 Embedding 对照实验

足以。基线覆盖 132 个唯一 Query，指标规则有测试，失败样本可检查，并且 Recall@5 仍有 9 个明确未命中，给 Embedding 对照留下了可验证的提升空间。下一轮必须沿用同一 Query、Corpus、Relevant Document 映射和指标定义，不能重新挑样本。

## 11. 已知限制

- Corpus 是 RAGBench 已提供候选文档的并集，不是完整电子手册知识库；93.18% Recall@5 不能解释为真实全库效果。
- 每个 Query 原本已有预先候选文档；取所有候选的并集只能制造有限的跨 Query 干扰，不能替代从与 Query 无关的完整资料库中检索。
- 缺少原始 PDF、OCR、版面、页码、标题层级和源到段落的转换记录，因此不能评价资料解析、切块和元数据构建质量。
- `validation + test` 被共同作为一次性最终评测集合，没有独立开发集；本轮没有调参，但未来若调参必须另建开发划分。
- 每个 Split 的 132 行实际只有 66 个唯一 Query；本轮按 Query 合并上下文，避免重复加权。
- 1 条源记录缺少相关键，依赖同 Query 的另一条有效记录完成映射。
- Relevant Document 来自模型辅助的句级标注，可能存在争议，并非完全人工金标准。
- 查询耗时未包含进程启动、数据加载和索引构建时间。

## 12. 下一轮建议

下一轮最值得验证的单一假设是：对一小批可追溯的原始手册文件，能否稳定完成解析、必要的 OCR、版面/标题识别、切块和页码等元数据构建，并让每个检索文本单元可回溯到原始位置。该前处理能力必须作为独立迭代验证，不混入本轮，也不在此自动开始。
