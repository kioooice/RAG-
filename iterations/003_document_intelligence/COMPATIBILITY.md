# Docling 兼容性与资源结论

核实日期：2026-07-12。

## 官方兼容性

| 项目 | 结论 |
|---|---|
| 固定版本 | `docling==2.111.0` |
| Windows | 官方安装文档明确支持 Windows x86_64/arm64 |
| Python | 官方 FAQ 说明从 2.59.0 起支持 Python 3.14；本轮实际使用 3.14.2 |
| 许可 | Docling 代码 MIT；各模型仍需遵守其原始包许可 |
| 本地运行 | 可完全本地及隔离网络运行；前提是模型已预取并通过 `artifacts_path` 指定 |
| 计算设备 | PDF 布局和表格模型支持 CPU；本轮未启用 CUDA，显存使用为 0 |
| 支持格式 | 官方列出 PDF、图片、DOCX、PPTX、XLSX 等；本轮逐一实测 |

官方依据：

- 安装与 Windows 支持：https://docling-project.github.io/docling/getting_started/installation/
- Python 3.14、离线运行与模型说明：https://docling-project.github.io/docling/faq/
- 支持格式：https://docling-project.github.io/docling/usage/supported_formats/
- PyPI 版本与 MIT 许可：https://pypi.org/project/docling/

## 隔离方案

- 主项目环境保持为 `D:\Projects\study\retrieval-adaptation-lab\.venv`，没有安装 Docling。
- Docling 环境：`D:\AI-Lab\envs\retrieval-adaptation-lab-docling`。
- 模型：`D:\AI-Lab\models\docling\2.111.0`。
- pip、Hugging Face、Torch 缓存继续位于 `D:\AI-Lab\cache`。
- 未修改 PATH、用户环境变量或系统环境变量。

直接依赖见 `requirements-docling.txt`。Docling 2.111.0 的默认 RapidOCR 路径不会自动安装 ONNX Runtime，因此显式固定 `onnxruntime==1.27.0`；混合路由复用 002 模块，因此保留 `pypdf==6.14.2`。

## 下载与磁盘预算

- 安装前解析出的 104 个 Python wheel：约 0.315 GiB 下载。
- 官方 `ds4sd/docling-models` 元数据核算：约 0.334 GiB；实际按 `layout tableformer rapidocr` 预取后的模型目录为约 0.590 GiB。
- 独立环境安装后约 1.34 GiB。
- 总量没有触发 3GB 新增下载停止线。

首次安装命令超时后遗留子进程，造成一次 WinError 32 文件锁；终止仅属于本轮安装的两个进程后安装成功。`pip check` 通过。
