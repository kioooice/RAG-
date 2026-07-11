# 001：证据检索基线

## 本轮目标

使用公开 RAGBench `emanual` 测试集建立不依赖大模型、Embedding 或向量数据库的 TF-IDF 基线，验证问题能否从固定语料中找回至少一个标注相关文档。

## 技术方法

- 数据入口固定为 `galileo-ai/ragbench`，版本固定为 `97808f3e5fd16ede40bbff6c2949af8139b2eb7b`。
- 数据卡中的 `test` 132 行实际只有 66 个唯一 Query，每个 Query 有两条不同上下文记录；为满足至少 100 个不重复 Query，固定合并 `emanual/validation` 与 `emanual/test`，按 `query_id + question` 合并上下文后得到 132 个唯一 Query。随机种子 `20260711` 仅用于确定处理顺序。
- 把全部测试样本的候选 `documents` 合并为语料，以规范化文本的 SHA-256 前 16 位生成稳定 Document ID，并确定性去重。
- TF-IDF 配置在查看指标前固定：英文词级 1–2 gram、lowercase、L2 norm、sublinear TF、`min_df=1`。
- Recall@K 使用“前 K 项命中任意一个相关文档”的二元定义；多个相关文档时 MRR 取首次命中的倒数排名。

## 数据范围

- 公开数据，不使用公司资料。
- 只读取 `emanual/validation` 与 `emanual/test`，合计仍小于整个 `emanual` 配置约 2.29 MB 的压缩下载量，不下载完整 RAGBench。
- 原始与处理数据只进入 D 盘 Hugging Face 缓存和 `data/processed`，不提交 Git。

## 验收标准

- 至少评测 100 条 Query，本轮实际目标为全部 132 条。
- 生成 Recall@1/3/5、MRR、查询耗时、语料规模和未命中数。
- 指标规则有自动化测试；提供至少 20 条 Recall@5 未命中，或不足时补充低排名/低分命中。
- CLI 能对同一语料输出 Top-5 文档、分数和摘要。
- 原项目验证与 `pip check` 通过，结果可重复生成。

## 明确不做

- 不使用答案文本构造 Query，不用测试集调参。
- 不使用大模型、Embedding、PyTorch、Transformers、向量数据库或 RAG 框架。
- 不开发网页，不修改 Notebook 学习内容，不开始下一轮 Embedding 实验。

## 可能风险

- `documents` 是数据集已提供的候选上下文，不是原始完整电子手册知识库。
- 相关文档由句级相关性键推导，标注本身可能有模型判断偏差。
- `validation` 有 1 条源记录的相关键为空；它只贡献候选文档和参考答案，同 Query 的另一条有效记录负责相关文档映射。若任何 Query 合并后仍无映射，处理脚本会失败。
- 把所有测试候选文档合并为语料会引入跨 Query 干扰，但仍小于真实知识库规模。
- TF-IDF 依赖词面重合，对同义表达、拼写错误和长文档较弱。
