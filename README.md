# Retrieval Adaptation Lab

这是一个面向个人长期学习的检索与模型适配实验仓库，覆盖 RAG、Embedding、向量数据库、文档建库、RAG 评测，以及 LoRA/QLoRA、Embedding 和 Reranker 微调。

本项目优先保留可观察、可修改的技术过程，不把解析、切块、向量化、检索、重排序或生成完全封装成黑盒。

## 当前阶段

第一阶段只建立可复现的 Python/Jupyter 环境和 RAG 数据结构认知，不安装深度学习框架、向量数据库、RAG 框架或微调工具，也不下载模型权重和完整数据集。

## 快速开始（Windows PowerShell）

```powershell
.\scripts\start_lab.ps1
```

在 Jupyter 中选择内核 `retrieval-adaptation-lab`，打开 `notebooks/01_dataset_and_rag_structure.ipynb`。

如需先检查环境与缓存位置：

```powershell
.\.venv\Scripts\python.exe scripts\show_cache_locations.py
.\.venv\Scripts\python.exe scripts\check_environment.py
.\.venv\Scripts\python.exe scripts\verify_setup.py
```

## 项目位置与存储规则

- 当前正式项目位于 `D:\Projects\study\retrieval-adaptation-lab`。
- C 盘原目录仅作为迁移前副本保留，不再写入新内容，也不得删除。
- Hugging Face、Torch 与 pip 缓存统一写入 `D:\AI-Lab\cache`；大型数据与模型分别写入 `D:\AI-Lab\data` 和 `D:\AI-Lab\models`。
- 下载数据集或模型前必须先报告预计大小；模型权重、数据集缓存、本地环境和密钥不得提交 Git。
- 项目脚本应从自身位置推导项目根目录，避免写死用户目录。

## 目录说明

- `notebooks/`：可阅读、可运行的学习与实验过程。
- `data/`：原始、处理后和评测数据；默认不提交实际数据。
- `src/`：按 RAG 技术环节拆分的可复用代码。
- `experiments/`：配置、结果和实验报告。
- `scripts/`：环境检查和项目验证脚本。
- `models/`：模型说明或本地模型位置；模型权重不提交 Git。

依赖的直接用途和实际安装版本见 `requirements.txt`。后续新增核心依赖时必须先说明用途。
