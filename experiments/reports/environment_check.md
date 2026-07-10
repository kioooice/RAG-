# 本机环境检查（2026-07-11，迁移前记录）

> **仅限本地，不得直接公开。** 本报告包含用户目录、硬件配置、磁盘空间和本机工具路径等环境信息；公开前必须人工脱敏。

> 本文保留的是迁移到 D 盘前的历史环境快照，其中的 C 盘路径不再作为项目启动或执行路径。当前状态请运行 `scripts\show_cache_locations.py` 和 `scripts\verify_setup.py` 查看。

检查原则：只读收集系统信息；未执行系统级安装，未修改 PATH、注册表、防火墙或环境变量。

## 已满足

- 工作目录：`C:\Users\Administrator\Documents\Codex\2026-07-11\rag-embedding-rag-lora-qlora-embedding`。
- 当前目录不是已有 Git 项目，原有内容只有 Codex 的 `outputs/` 与 `work/`；目标子目录此前不存在。
- Windows 11 专业版，64 位，版本 10.0.22631（Build 22631）。
- Shell：PowerShell 7.6.3 Core（`pwsh`）。
- CPU：AMD Ryzen 5 6600H，6 核 12 线程。
- 内存：15.24 GB，总检查时可用约 3.59 GB。
- NVIDIA GPU：GeForce RTX 4050 Laptop GPU，6141 MiB 显存；检查时约 5119 MiB 可用。
- NVIDIA 驱动：595.79；驱动报告最高 CUDA 兼容版本 13.2。
- Python：3.14.2，`C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe`。
- pip：25.3，属于上述 Python 3.14 安装。
- Python 标准库 `venv` 可用。
- Git：2.52.0.windows.1，`C:\Program Files\Git\cmd\git.exe`。
- VS Code：1.116.0 x64，命令位于 `D:\Developer Tools\Microsoft VS Code\bin\code.cmd`。
- WSL：WSL 2.7.10 已安装；当前未列出 Linux 发行版。
- 端口 6333、8000、8501、8888 均未被监听占用。
- 磁盘：C 盘总计约 100.01 GB、可用 8.54 GB；D 盘总计约 375.94 GB、可用 262.37 GB。

## 缺失但当前阶段不需要

- Docker 与 Docker Compose 命令未发现。
- CUDA Toolkit / `nvcc` 未发现。注意：NVIDIA 驱动支持 CUDA 不等于已安装 CUDA Toolkit。
- 全局 Jupyter 与 ipykernel 未发现；本阶段会只安装到项目 `.venv`。
- VS Code 未发现 Python、Jupyter 或 Pylance 扩展；可以先用浏览器版 Jupyter，不阻塞脚本和 Notebook。
- WSL 未安装 Linux 发行版；本阶段使用原生 Windows Python。

## 缺失且会阻塞当前阶段

- 暂无。Python、pip、Git、可写磁盘和标准 `venv` 均可用。

## 存在版本或路径冲突

- PATH 同时包含真实 Python 3.14 与 Microsoft Store 的 `WindowsApps` Python 占位程序；当前 `python` 正确解析到真实 Python 3.14。
- 仅发现一个实际 Python 运行时（3.14）。其版本较新，科学计算包是否都有兼容轮子需要在项目 `.venv` 内验证。
- `uv 0.10.7` 命令存在，但其默认缓存路径 `C:\Users\Administrator\AppData\Local\uv\cache` 初始化失败（目标已作为文件存在）。本轮不修改该路径，也不使用 `uv`。
- C 盘可用空间只有约 8.54 GB，足够本阶段的小环境，但不适合后续直接存放大型模型或数据集。

## 后续阶段才需要

- Docker/Compose：本地运行 Qdrant 等服务时再评估。
- 深度学习框架及配套 CUDA 运行时：进入模型推理或微调前，按显卡和框架版本选择。
- Qdrant、RAG 框架、LoRA/QLoRA、Embedding/Reranker 微调工具：均不在第一阶段安装。
- 大型模型权重与完整数据集：先估算显存、内存、磁盘、时间和下载量，再单独确认。

## 当前资源判断

RTX 4050 Laptop 的 6 GB 显存可支持小模型推理、部分量化与小规模适配实验，但后续 QLoRA 的模型大小、上下文长度和 batch size 必须保守规划。C 盘空间是更直接的风险，后续模型缓存宜另行规划到空间充足的位置，但本轮不修改任何系统或用户环境配置。

## 项目环境建立后的结果

- 已由 Python 3.14.2 创建项目 `.venv`，未向全局 Python 安装包。
- 第一阶段 7 个直接依赖均成功安装和导入；精确版本见 `requirements.txt`。
- 已注册 Jupyter Kernel `retrieval-adaptation-lab`。
- 安装完成后 C 盘可用约 7.60 GB；本轮环境新增占用约 0.94 GB。
- `pip check` 返回 `No broken requirements found.`。
- 项目验证脚本全部通过，Notebook 已在内存中完整执行，未下载数据或模型。
