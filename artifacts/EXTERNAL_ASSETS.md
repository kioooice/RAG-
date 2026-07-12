# 外部资产清单

本文件只记录恢复所需的名称、版本、来源和校验信息，不提交模型、缓存、数据集或运行时本体。每台电脑的实际路径由 `config/machine.local.ini` 覆盖；本文件中的 D 盘路径只是当前机器默认值。

## 数据集与小型实验数据

| 资产 | 版本/Revision | 当前用途 | 生成/恢复命令 |
|---|---|---|---|
| `galileo-ai/ragbench` / `emanual` | revision `97808f3e5fd16ede40bbff6c2949af8139b2eb7b` | 001 TF-IDF 152/221 Corpus、132 Query历史基线 | `D:\Projects\study\retrieval-adaptation-lab\.venv\Scripts\python.exe scripts\prepare_emanual.py --query-count 132 --seed 20260711` |
| 002 MX-100虚构材料 | 项目脚本生成，无外部revision | 003/004/005–009受控测试 | `D:\Projects\study\retrieval-adaptation-lab\.venv\Scripts\python.exe scripts\generate_ingestion_fixture.py` 与 `node scripts\build_ingestion_office_fixtures.mjs` |

固定数据校验：001 `corpus.jsonl` SHA-256 `56011E4BB78798F37CA97CCEF33048C26B1B1A6EBE3EDE45F48EA370E0CC8B52`；221 Corpus SHA-256 `91C33A8C4C8A7A737722C6045EC42DEEFDA6D718D924D46974B929883D870D18`；Query文件 SHA-256 `4C67061BD76B4BAC3EB254D05CAF7B6C558A88940A20E1B9F4C8017D7689BFEA`。

## Document Intelligence

- Docling `2.111.0`，许可证 MIT；独立环境 `retrieval-adaptation-lab-docling`。
- 模型目录默认：`D:\AI-Lab\models\docling\2.111.0`；包含 `ds4sd/docling-models` 与 `docling-project/docling-layout-heron` 资产。
- 003记录的模型目录大小约 `633,340,089` bytes；模型仓库commit/SHA-256未在当时资源报告中锁定，恢复时必须以官方Docling模型预取命令和本地清单重新确认，不在此处编造哈希。
- 当前下一阶段必需：主 `.venv`、Docling独立环境、Docling artifacts和002虚构材料。OCR模型只在验收需要时恢复。

## 检索

- `BAAI/bge-m3`，revision `5617a9f61b028005a4858fdac845db406aefb181`，MIT；模型目录默认 `D:\AI-Lab\models\bge-m3\5617a9f61b028005a4858fdac845db406aefb181`。
- 004实际选择性模型目录约 `2,293,339,869` bytes；单一模型文件SHA-256未锁定，revision是恢复时的主要身份。
- 当前默认检索结论：BGE-M3 Dense；Hybrid未成为默认方案。BGE-M3不是下一次Document Intelligence筛选的必需资产，可以暂不下载。

## 本地生成与运行时（历史对照）

- llama.cpp release `b9968`，MIT；默认运行时 `D:\AI-Lab\runtimes\llama.cpp\b9968\llama-server.exe`。发行包/二进制SHA-256未锁定；恢复时从官方release重新下载并记录本机哈希。
- Qwen3-4B-Instruct-2507 Q4_K_M：官方基座revision `cdbee75f17c01a7cc42f958dc650907174af0554`；第三方GGUF revision `a06e946bb6b655725eafa393f4a9745d460374c9`；文件SHA-256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`。
- Qwen3.5-9B Q4_K_M：官方基座revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`；第三方GGUF revision `3885219b6810b007914f3a7950a8d1b469d598a5`；文件SHA-256 `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8`。
- Qwen GGUF、llama.cpp和BGE环境只作为历史复现实验资产，当前下一阶段可以暂不下载。MiMo Key和配置永不进入Git同步内容。

## 恢复原则

1. 大型资产缺失时只报告缺失、官方来源和预计大小，不由 `bootstrap_machine.ps1` 自动下载超过500MB的内容。
2. 下载前重新核对官方revision、许可、预计大小和SHA-256。
3. 资产路径只进入机器本地配置，不写死在另一台电脑的脚本中。
