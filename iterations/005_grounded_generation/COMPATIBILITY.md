# 005 兼容性与来源预检

预检日期：2026-07-12（Asia/Shanghai）

复核入口：

- 官方模型卡：https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- 官方模型 LICENSE：https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/LICENSE
- 量化仓库：https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF
- llama.cpp release：https://github.com/ggml-org/llama.cpp/releases/tag/b9968
- llama.cpp LICENSE：https://github.com/ggml-org/llama.cpp/blob/master/LICENSE

## 基础模型

- 官方仓库：`Qwen/Qwen3-4B-Instruct-2507`
- 许可证：Apache-2.0（官方 LICENSE）
- 官方模型 revision：`cdbee75f17c01a7cc42f958dc650907174af0554`；量化文件上传前可见的权重/配置 revision 为 `eb25fbe4f35f7147763bc24445679d1c00588d89`（模型文件哈希在这两个 revision 间未改变）。
- 参数量：4.0B；原生上下文 262,144；官方说明该变体仅支持 non-thinking mode。
- 本轮实际上下文：8192，原因是虚构资料短且要控制 CPU 内存。

## GGUF 量化文件

- 仓库：`unsloth/Qwen3-4B-Instruct-2507-GGUF`
- 量化创建者：Unsloth（仓库 card 的 `base_model` 指向官方 Qwen 仓库；不是仅按下载量选择）。
- 文件：`Qwen3-4B-Instruct-2507-Q4_K_M.gguf`
- 文件首个包含提交：`cfee99622e72553c7e06abfbe9b74a40269d0e94`；仓库当前 revision：`a06e946bb6b655725eafa393f4a9745d460374c9`
- 大小：2,497,281,120 bytes（约 2.50 GB）
- HF LFS SHA-256：`3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`
- 本地下载后 SHA-256：与上述值完全一致。
- 追溯判断：官方模型卡链接、GGUF card 的 `base_model`、锁定的官方权重/配置 revision、量化仓库提交和文件哈希形成可复核链；量化发布者没有在 README 中给出转换命令与基座 commit 的机器可验证绑定，因此该链标记为“第三方可追溯，非官方量化声明”，不是无条件信任。

## llama.cpp

- 项目：`ggml-org/llama.cpp`
- 固定 release：`b9968`（2026-07-12）；许可证 MIT。
- Windows x64 CPU 包：`llama-b9968-bin-win-cpu-x64.zip`，18,211,732 bytes；未写入 PATH，解压到 `D:\AI-Lab\runtimes\llama.cpp\b9968`。
- 运行模式：本轮使用 CPU 后端（`-ngl 0`）和本机 `127.0.0.1` 服务；`--offline` 防止运行时联网。
- 官方发行包同时提供 CUDA 12.4/13.3 和 Vulkan 变体；本轮没有下载 CUDA DLL、没有安装 CUDA Toolkit，也没有修改系统 PATH。RTX 4050 Laptop GPU（6141 MiB，驱动 595.79）已被系统识别，但本轮不以 GPU 结果作为验收条件。

## 下载与环境预算

- 模型 2.50 GB + CPU runtime 17.4 MB，预计/实际新增下载约 2.52 GB，低于 3 GB 停止阈值。
- 模型：`D:\AI-Lab\models\qwen3-4b-instruct-2507\unsloth-a06e946bb6b655725eafa393f4a9745d460374c9`
- runtime 日志与独立目录：`D:\AI-Lab\envs\retrieval-adaptation-lab-llama-cpp`
- 主 `.venv`、Docling 环境和 BGE 环境未被安装包污染；没有新增 Python 依赖。

## 实际运行观察

- Python：3.14.2，独立使用已有 BGE 环境 `D:\AI-Lab\envs\retrieval-adaptation-lab-bge-m3`；`pip check` 输出 `No broken requirements found.`
- llama.cpp 服务 CPU 峰值 RSS：约 7.98 GB；评测进程峰值 RSS：约 1.88 GB；合计约 9.30 GiB。
- 本轮 `-ngl 0`，模型没有卸载到 GPU；运行时观察到的 GPU 已用显存约 669 MiB 是整机基线观察，不作为模型显存指标。
- RTX 4050 Laptop GPU：6141 MiB，驱动 595.79；本轮没有安装 CUDA Toolkit、没有修改 PATH。
- 本轮实际新增模型和运行时下载合计约 2.52 GB；评测运行使用 `--offline`，生成结束后服务已关闭。
- 详细机器可读记录见 `resource_report.json`；生成输出和失败来源见 `generation_results.jsonl`、`failures.csv`。
