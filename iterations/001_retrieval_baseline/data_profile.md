# RAGBench emanual 数据画像

## 数据集与许可

- 正式名称：[`galileo-ai/ragbench`](https://huggingface.co/datasets/galileo-ai/ragbench)。
- 历史入口：`rungalileo/ragbench`；Hugging Face API 当前将其解析到相同正式 ID 与相同版本，不作为另一数据源使用。
- 固定版本：`97808f3e5fd16ede40bbff6c2949af8139b2eb7b`。
- 配置与 Split：`emanual` / `validation + test`。
- 许可：CC BY 4.0；使用和再发布时需要保留合理署名，并遵守许可条款。
- 规模：`emanual` 三个 Split 合计下载约 2,292,660 字节、解压约 12,222,593 字节；数据卡显示 `validation` 和 `test` 各 132 行。实际检查发现每个 Split 各只有 66 个唯一 `query_id/question`，每个 Query 对应两条不同上下文记录；两个 Split 之间无 Query 重叠，合并上下文后得到 132 个唯一 Query。

## 正式字段

`id`、`question`、`documents`、`response`、`generation_model_name`、`annotating_model_name`、`dataset_name`、`documents_sentences`、`response_sentences`、`sentence_support_information`、`unsupported_response_sentence_keys`、`adherence_score`、`overall_supported_explanation`、`relevance_explanation`、`all_relevant_sentence_keys`、`all_utilized_sentence_keys`、`trulens_groundedness`、`trulens_context_relevance`、`ragas_faithfulness`、`ragas_context_relevance`、`gpt3_adherence`、`gpt3_context_relevance`、`gpt35_utilization`、`relevance_score`、`utilization_score`、`completeness_score`。

字段由 Hugging Face 数据卡元数据与 datasets-server 的 `emanual/train` 样本共同核实，没有根据名称猜测结构。

## 本实验的字段映射

- Query：直接使用 `question`，只规范化空白，不拼接 `response`。
- Candidate Documents / Corpus：每条源记录的 `documents` 已包含 3 个候选文档；同一 Query 的两条源记录先合并候选和相关文档，再把 132 个唯一 Query 的候选文档合并后确定性去重，形成共享 Corpus。
- Relevant Document：读取 `all_relevant_sentence_keys`，例如 `2e` 的数字前缀 `2` 映射到 `documents[2]`。Streaming 检查确认 `test` 的 132 条源记录均可映射；合并 `validation + test` 后，132 个唯一 Query 最终也都至少映射到 1 个文档且没有越界。
- 映射异常：`validation` 有 1/132 条源记录的 `all_relevant_sentence_keys` 为空；同一 Query 的另一条记录存在有效映射。空键记录不贡献 Relevant Document，但仍保留其候选文档与参考答案；132 个合并 Query 最终全部有至少一个有效相关文档。
- Generated Response：同一 Query 的两条记录使用完全相同且顺序一致的 `documents`，但 `generation_model_name` 分别是 `gpt-3.5-turbo-0125` 与 `claude-3-haiku-20240307`，两者生成的 `response` 均不同。`response` 是 Generated Response，不是 Reference Answer 或 Ground Truth。处理数据为兼容已生成产物保留旧字段名，但当前检索、相关文档映射、TF-IDF拟合、排序和指标均未读取或使用这些文本。
- Document ID：规范化文档文本 SHA-256 的前 16 位，格式为 `doc_<hex>`；相同段落在所有位置得到同一 ID。

## 候选文档与完整知识库的区别

数据已经为每个 Query 提供候选 `documents`，但没有在本配置中提供原始完整电子手册的独立全库。本实验不是在单条记录自己的候选中排序，而是把 `validation + test` 所有候选合并成一个共享 Corpus 后检索，因此能测试跨 Query 干扰；它仍不能代表在完整产品手册库、切块策略和更大语料规模下的端到端检索效果。

## 文档前处理边界

- `documents` 字段已经是可直接读取的文本字符串列表，`documents_sentences` 还提供了句级拆分。对本实验而言，每个 `documents[i]` 已经是一个可索引的文档/段落单元；本轮没有再次切块。
- 数据字段没有提供原始 PDF、页面图像、OCR 结果、版面坐标、标题层级、页码或完整的源文件到段落转换记录。因此无法从当前数据可靠判断这些文本最初如何从手册中抽取、是否经过 OCR、官方采用了什么切块规则，或哪些原始元数据在整理时被丢失。
- 本轮直接使用已经抽取或整理后的文本，不包含 PDF 解析、OCR、版面恢复、清洗、切块策略设计和元数据构建，也没有完成“资料建库”。
- 每个 Query 的候选文档由数据集预先提供。本轮将所有评测 Query 的候选文档取并集后再做全局排序，虽然比“只在当前 Query 的几个候选内排序”更严格，但语料边界仍由预先候选决定。
- 真实全局知识库检索通常从与 Query 无关的完整资料库出发，需要先完成文件解析、切块、稳定元数据和全库索引；其文档数量、噪声、重复、跨页结构与召回难度都可能明显更高。
- PDF/OCR/版面/切块/元数据等前处理能力不在本轮实现范围，将作为独立能力另行验证。

## 可能偏差

- Query 包含拼写错误和非标准表达，可能降低纯词法检索。
- 候选文档来自既有 RAG 流程，分布可能比完整知识库更接近问题。
- 由于缺少原始文件和前处理记录，本轮无法评价解析、OCR、版面恢复、切块质量或元数据召回贡献。
- `response` 是生成模型输出，不是参考答案或人工 Ground Truth；相关文档来自模型辅助的句级标注，也不是完全无误的人工金标准。
- 相同或近似手册段落可能重复出现；本实验只对完全规范化后相同的文本去重。
- 数据卡行数不能直接当作唯一 Query 数；本实验显式合并同 ID、同问题的两条上下文记录，避免重复加权。
- 测试集全部用于最终评测，没有使用测试结果选择 TF-IDF 参数。

## 元数据来源

- [Hugging Face 数据卡](https://huggingface.co/datasets/galileo-ai/ragbench)
- [Hugging Face 数据集 API](https://huggingface.co/api/datasets/galileo-ai/ragbench)
- [datasets-server 配置与字段信息](https://datasets-server.huggingface.co/info?dataset=galileo-ai/ragbench)

## 152段与221段Corpus边界

- 原152段Corpus是`validation + test`中792次`documents`出现按规范化文本确定性去重的结果，原指标和失败文件保持不变。
- 221段对照只从`train`读取`documents`字段的3,162次文档出现，不读取或使用train的Query、Generated Response、相关性键或其他标签。与原152段合并去重后新增69段，得到221段。
- 221段不是已证明完整的原始手册知识库，只是固定版本RAGBench `emanual/train/validation/test`中公开`documents`的规范化并集。
- 152段与221段都使用相同TF-IDF配置和同一组132个Validation/Test Query；详细结果见`CORPUS_COMPARISON.md`与`corpus_ranking_changes.csv`。
- Corpus扩展后必须重新拟合TF-IDF。文档频率分母和词项出现频率均发生变化，因此共有词项的IDF权重也会变化，结果差异不只是多了69个竞争文档。
