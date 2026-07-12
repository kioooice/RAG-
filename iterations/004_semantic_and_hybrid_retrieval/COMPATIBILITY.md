# BGE-M3 兼容性预检

核实日期：2026-07-12。

## 固定模型

- 模型：`BAAI/bge-m3`
- revision：`5617a9f61b028005a4858fdac845db406aefb181`
- 模型许可：MIT
- FlagEmbedding 代码许可：MIT；本轮没有安装 FlagEmbedding 训练工具。
- 推理库：`sentence-transformers==5.6.0`，Apache-2.0。

官方模型卡给出的 Dense 规格为 1024 维、最大 8192 tokens，并明确说明 BGE-M3 检索 Query 不再需要 instruction：https://huggingface.co/BAAI/bge-m3 。FlagEmbedding 项目与代码许可：https://github.com/FlagOpen/FlagEmbedding 。

## 运行兼容性

- Windows 11、Python 3.14.2：实际安装和离线推理通过。
- CPU：使用 PyTorch `2.13.0+cpu` 正式评测。
- GPU：检测到 RTX 4050 Laptop 6GB、驱动 595.79。Sentence Transformers 支持通过 `device="cuda:0"` 推理，但本轮没有安装 CUDA PyTorch，因此显存峰值记录为 0。
- 6GB 显存理论上可容纳 FP16 约 1.1GB 权重及本轮短文本推理，但正式兼容性仍需使用对应 CUDA wheel 实测，不能把“检测到GPU”写成“GPU已验证”。

Sentence Transformers 当前版本要求 Python ≥3.10，提供 CPU/CUDA device 参数：https://pypi.org/project/sentence-transformers/ 、https://www.sbert.net/examples/sentence_transformer/applications/computing-embeddings/README.html 。

## 下载治理

Hugging Face 完整仓库约 4.27GiB，因包含 PyTorch 与 ONNX 两套大权重，超过 3GB 停止线，因此没有整库下载。

只下载固定 Dense 必需的 12 个文件：

- `pytorch_model.bin` 与模型配置；
- tokenizer、SentencePiece、Pooling 和 Sentence Transformers 配置；
- 排除整个 `onnx/`、图片、`sparse_linear.pt` 和 `colbert_linear.pt`。

实际选择性模型目录约 2.136GiB；Python wheel 预估约 0.200GiB，总新增下载约 2.336GiB，未触发 3GB 停止线。

## 隔离位置

- 环境：`D:\AI-Lab\envs\retrieval-adaptation-lab-bge-m3`
- 模型：`D:\AI-Lab\models\bge-m3\5617a9f61b028005a4858fdac845db406aefb181`
- 缓存：`D:\AI-Lab\cache`
- 向量与索引：`D:\AI-Lab\data\retrieval-adaptation-lab\retrieval_004`

没有修改系统 PATH、用户环境变量、主 `.venv` 或 Docling 环境。
