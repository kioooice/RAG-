# 迁移到 D 盘 study 工作区

> **仅限本地，不得直接公开。** 本报告包含用户目录和本机项目路径等环境信息；公开前必须人工脱敏。

迁移日期：2026-07-11

## 路径

- 源项目：`C:\Users\Administrator\Documents\Codex\2026-07-11\rag-embedding-rag-lora-qlora-embedding\retrieval-adaptation-lab`
- 目标项目：`D:\Projects\study\retrieval-adaptation-lab`
- 迁移方式：复制并验证；未移动、删除或继续修改源项目。

## 复制结果

- 源项目原始文件：28,996 个，共 736,994,706 字节（主要空间来自旧 `.venv`）。
- 纳入复制和哈希验证：43 个文件，共 51,559 字节。
- 复制前后 SHA-256 清单摘要：`7C0DE91F9A5E86AD3EDB05F29B343581D2B91D6E453BFDDDC9622B26FE6B2DA9`。
- 排除目录：`.venv`、`__pycache__`、`.pytest_cache`、`.ipynb_checkpoints`、本地缓存、临时目录和下载目录。
- 排除文件：Python 字节码、临时文件、备份文件和未完成下载文件。
- `.git`、项目文档、配置、Notebook、源码、脚本，以及 `data`、`models` 等目录结构均已保留。

## 环境重建

- Python：3.14.2。
- 新虚拟环境：`D:\Projects\study\retrieval-adaptation-lab\.venv`。
- 依赖从迁移后的 `requirements.txt` 安装，pip 缓存使用 `D:\AI-Lab\cache\pip`。
- `pip check`：通过，无损坏依赖。
- 未安装 PyTorch、Transformers 或 Qdrant；未下载数据集或模型。
- Jupyter Kernel `retrieval-adaptation-lab` 已更新为 D 盘新 `.venv` 解释器。

## 缓存与启动

- Hugging Face：`D:\AI-Lab\cache\huggingface`
- Torch：`D:\AI-Lab\cache\torch`
- pip：`D:\AI-Lab\cache\pip`
- 数据：`D:\AI-Lab\data`
- 模型：`D:\AI-Lab\models`
- 启动命令：`.\scripts\start_lab.ps1`

## 验证

- `scripts\show_cache_locations.py`：通过；五个缓存变量均位于 D 盘、目录存在且可写。
- `scripts\check_environment.py`：完成；项目根目录和 Python 解释器均位于 D 盘。
- `scripts\verify_setup.py`：全部通过。
- `pip check`：通过。
- Python 源码编译：通过。
- Notebook：通过 nbformat 4 结构验证，并使用项目 Kernel 在内存中完整执行；未覆盖源 Notebook。
- `scripts\start_lab.ps1`：PowerShell 语法通过，并以 `--help` 完成启动链路冒烟检查。
- Jupyter Kernel：同名旧 Kernel 已更新，解释器为 D 盘新 `.venv`。
- Git：仓库完整性检查通过，当前为尚无提交的 `main` 分支；迁移后的文件和配置仍为未跟踪状态。
- 源项目复核：原始文件数仍为 28,996、总字节数仍为 736,994,706；有效文件摘要与复制前一致，复制开始后没有源文件被修改。
- 下载复核：`D:\AI-Lab` 除 pip 包缓存外没有数据或模型文件。
