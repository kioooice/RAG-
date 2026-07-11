# TF-IDF Corpus规模收口对照

## 约束

- 检索方法、代码路径与TF-IDF配置完全相同，没有调参或重新选择特征。
- 评测Query仍是相同的Validation 66题与Test 66题。
- 152段原结果及`metrics.json`、`failures.csv`保持不变。
- 221段由原152段加上`emanual/train`中只读取`documents`字段后新增的69段组成；没有读取train的Query、Generated Response或相关性标签。
- 没有查看或针对Test失败内容调整任何配置。

## 分Split指标

| Split | Corpus | Recall@1 | Recall@3 | Recall@5 | MRR | 平均查询耗时(ms) | Top-5失败 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Validation | 152 | 0.6212 | 0.9091 | 0.9394 | 0.7568 | 0.8068 | 4 |
| Validation | 221 | 0.5152 | 0.8182 | 0.9091 | 0.6811 | 0.9318 | 6 |
| Test | 152 | 0.6667 | 0.8333 | 0.9242 | 0.7644 | 0.8244 | 5 |
| Test | 221 | 0.6061 | 0.8030 | 0.8485 | 0.7093 | 0.9867 | 10 |

耗时是本机单次运行的小Corpus内存查询结果，亚毫秒级差异容易受系统噪声影响；它不能用于推断大型知识库性能。

## 排名变化

- 改善：0题。
- 下降：33题。
- 不变：99题。
- 全部132题的Split、152段排名、221段排名与变化类别见`corpus_ranking_changes.csv`。

下降题如下（V=Validation，T=Test）：

`emanual_1(T)`、`emanual_116(T)`、`emanual_176(T)`、`emanual_19(T)`、`emanual_257(T)`、`emanual_282(T)`、`emanual_283(T)`、`emanual_284(T)`、`emanual_302(T)`、`emanual_341(T)`、`emanual_403(T)`、`emanual_451(T)`、`emanual_486(T)`、`emanual_490(T)`、`emanual_631(T)`、`emanual_101(V)`、`emanual_135(V)`、`emanual_146(V)`、`emanual_182(V)`、`emanual_186(V)`、`emanual_196(V)`、`emanual_212(V)`、`emanual_267(V)`、`emanual_325(V)`、`emanual_346(V)`、`emanual_377(V)`、`emanual_423(V)`、`emanual_437(V)`、`emanual_461(V)`、`emanual_470(V)`、`emanual_489(V)`、`emanual_529(V)`、`emanual_555(V)`。

221段时的Top-5失败：

- Validation 6题：`emanual_146`、`emanual_212`、`emanual_325`、`emanual_437`、`emanual_489`、`emanual_555`。
- Test 10题：`emanual_1`、`emanual_176`、`emanual_282`、`emanual_283`、`emanual_284`、`emanual_302`、`emanual_420`、`emanual_451`、`emanual_486`、`emanual_490`。

## IDF变化

- 152段词表特征：9,528。
- 221段词表特征：12,339。
- 共有特征：9,528。
- IDF发生变化的共有特征：9,528。

扩展Corpus后TF-IDF会重新计算文档频率和IDF。排名变化既来自69个新增文档参与竞争，也来自原有词项权重改变，不能只解释为“候选更多”。本次结果表明，在现有相关性标签下，扩容增加了干扰，没有改善任何Query的首个相关文档排名。
