# 能力卡：003 Document Intelligence

## 用户目标

验证成熟的 Docling 能否接入现有资料处理系统，为 PDF、扫描 PDF、图片、DOCX、PPTX、XLSX 提供解析、OCR、结构和来源定位，同时保持既有统一 Schema。

## 控制面决策

- 默认只验证 Docling；不安装 MinerU、PaddleOCR 或 Unstructured。
- CSV、JSON、Markdown 保留 002 的确定性解析器。
- 002 是对照与回退参考，不覆盖结果、不删除实现。
- 不做切块、Embedding、检索、RAG、微调或自研 OCR。

## 输入与输出契约

- 输入：002 的 12 个完全虚构文件和原 38 项 Ground Truth。
- 输出：现有 `DocumentRecord` 与 `KnowledgeUnit` 字段，不引入 Docling 专属上层 Schema。
- PDF/图片保留页码和区域；PPTX 保留幻灯片；XLSX 保留工作表和范围；DOCX 保留标题路径及顺序。
- 空文本、乱码或转换失败不得标记为 `accepted`。

## 验收标准

- 原 38 项检查不得删除或弱化，并应全部通过。
- 两个 `needs_ocr` 输入应产生含 `MX-100`、`75℃`、`E07` 的真实 OCR 文本、区域和置信度。
- 扩展名错误、重复和不支持文件的治理行为保持不变。
- 两次执行生成相同 Document ID 和 KnowledgeUnit ID。
- 环境与模型完全位于 D 盘，可在模型预取后离线重复执行。

## 成熟方案

- Docling 2.111.0，MIT；RapidOCR/ONNX Runtime 用于本地 CPU OCR。
- Windows 11、Python 3.14.2 独立项目环境。

## 风险与停止条件

- 风险：Office 来源定位粒度不完全一致；复杂表格可能合并或漏识别；中文旧式扫描 OCR 可能不稳定；CPU 峰值内存较高。
- 若受控测试质量可接受且没有严重追溯或稳定性问题，本轮停止，不比较其他工具。
- 只有中文 OCR、复杂 PDF/跨页表格或大规模多源摄取出现可复现关键失败时，才分别提出 PaddleOCR、MinerU 或 Unstructured；本轮不自动安装。
