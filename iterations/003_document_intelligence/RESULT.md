# 003 Document Intelligence 结果

## 结论

Docling 已通过受控接入验收，可以作为 PDF、图片和 Office 文档的优先解析器；CSV、JSON、Markdown 继续使用 002 的确定性解析器。原 38 项检查全部通过，新增 12 项 OCR 检查全部通过。当前证据满足停止条件，本轮不继续安装 PaddleOCR、MinerU 或 Unstructured。

## 实际路由

| 路由 | 格式 |
|---|---|
| Docling 2.111.0 | PDF、扫描 PDF、PNG、DOCX、PPTX、XLSX，以及实际内容为 PDF 的错误扩展名文件 |
| 002 确定性解析器 | CSV、JSON、Markdown |
| 治理层 | SHA-256 重复、扩展名/内容不一致、不支持文件 |

Docling 的 lossless JSON 被转换为原有 `DocumentRecord` 和 `KnowledgeUnit`，没有改变统一 Schema。`source_locator` 根据实际格式保存页码/坐标、图片区域、幻灯片、工作表/单元格范围或 DOCX 顺序；Docling 原始标签和阅读顺序放在 metadata 中。

## 受控结果

- 文件：12；DocumentRecord：12；KnowledgeUnit：38。
- 状态：`accepted=9`、`needs_review=1`、`duplicate=1`、`unsupported=1`、`failed=0`。
- 原 38 项 Ground Truth：38/38。
- OCR 扩展检查：12/12。
- 两次运行：Document ID、KnowledgeUnit ID 和去重结果一致。

### OCR 改善

- `mx100_scanned.pdf`：从 002 的 `needs_ocr` 变为 `accepted`；识别 151 个输出字符，保留 `MX-100`、`75℃`、`E07` 和区域坐标；OCR score 约 0.981。
- `mx100_image.png`：从 `needs_ocr` 变为 `accepted`；识别 155 个输出字符，保留三个关键字段和区域坐标；OCR score 约 0.976。
- 两者的三步维护流程均保留。没有读取生成脚本变量补齐解析结果。

### 与 002 的比较

- 改善：扫描 PDF、PNG 共 2 个。
- 退化：状态和原 38 项断言中没有发现。
- 不变：其余 10 个文件的治理状态保持一致。
- DOCX 标题层级被保留；样例表格中的空行在 002 和 Docling 中都为空，因此不是 003 新退化。

## 结构与来源定位

- 文本 PDF：页码、文本块和 bbox 可追溯。
- 扫描 PDF / PNG：OCR 文本、页码/图片名、区域和文档级 OCR 置信度可追溯。
- DOCX：`title`、`section_header`、列表和表格结构保留；没有 PDF 式物理页码，使用标题路径和文档顺序定位。
- XLSX：工作表名称、结构化网格和范围保留；范围由 Docling 的表格边界转换为 A1 表示。
- PPTX：幻灯片编号、正文、表格和 bbox 保留。
- 阅读顺序在受控材料上正确，但不应外推为所有复杂版面都可靠。

## 性能与资源

- 单文件 Docling 耗时：约 0.015 秒（XLSX）至 6.385 秒（PNG）；扫描 PDF 约 3.234 秒，文本 PDF 约 1.731 秒。
- 进程总 RSS 峰值观察最高约 1.53 GiB；这是复用同一进程时的总驻留峰值，不等于单文件增量。
- 独立环境约 1.34 GiB；模型约 0.590 GiB。
- CPU 执行，CUDA 不可用，显存 0。
- 模型预取后第二次运行不需要下载，并且确定性检查通过；因此可离线重复执行。完全断网将在最终验证中通过离线环境变量复核。

详细数据见 `metrics.json` 和 `resource_report.json`。

## 公开材料人工抽检（不计入受控指标）

下载日期均为 2026-07-12，材料存放在 D 盘实验数据目录，没有提交 Git。

1. **含表格文本 PDF**：NIST IR 8214C，来源 https://nvlpubs.nist.gov/nistpubs/ir/2026/NIST.IR.8214C.pdf 。NIST 技术系列的全球重印许可说明见 https://www.nist.gov/nist-research-library/nist-publications 。抽检 PDF 第 25 页：识别 2,531 字符、1 个结构化表格，页码和顺序正常。
2. **中文扫描 PDF**：《魯迅書簡》机械扫描，来源 https://commons.wikimedia.org/wiki/File:NLC416-05jh000872-2983_魯迅書簡.pdf ，页面声明为公共领域机械扫描。抽检第 1–3 页：第 1 页仅识别出极少文字；第 2–3 页识别 347 字符，OCR score 约 0.913，但存在繁体字误识别和目录顺序混乱。这是明确的中文旧式扫描边界。
3. **复杂版面 PDF**：NASA TM-84502，来源 https://ntrs.nasa.gov/api/citations/19820026424/downloads/19820026424.pdf 。NASA 政府作品使用说明见 https://sti.nasa.gov/disclaimers/ 。抽检第 54–55 页：识别 3,907 字符和 1 个表格，但图形/多栏内容仍需要人工检查阅读顺序。

这些材料只用于能力边界观察，不与 MX-100 的 50 项数字合并。

## 已知失败边界

- 旧式、低对比度、繁体中文扫描质量明显低于受控合成图片；“转换成功”不代表 OCR 内容可直接采用。
- Docling 提供文档/页面级置信度，不为每个最终 KnowledgeUnit 提供可直接解释的统一置信度。
- DOCX 没有物理页码；Office 定位语义与 PDF 不完全相同。
- 复杂 PDF 的跨页表格、公式、图形和多栏顺序尚未形成足够覆盖，不应宣称全面可靠。
- 当前峰值内存约 1.5 GiB，批量并行前必须单独做容量验证。

## 是否需要下一工具

- **PaddleOCR**：受控中文 OCR 已通过，但公开旧式中文扫描明显较弱。这是值得记录的候选证据，还不足以自动安装；应先明确真实资料是否包含同类旧扫描及验收阈值。
- **MinerU**：复杂公开 PDF 暴露人工复核需要，但尚无关键验收失败或跨页表格测试，因此证据不足。
- **Unstructured**：当前问题不是多数据源连接或大规模摄取，暂无引入证据。

## 复现

```powershell
$env:HF_HOME='D:\AI-Lab\cache\huggingface'
$env:HF_HUB_CACHE='D:\AI-Lab\cache\huggingface\hub'
$env:DOCLING_ARTIFACTS_PATH='D:\AI-Lab\models\docling\2.111.0'
$env:DOCLING_DEVICE='cpu'
D:\AI-Lab\envs\retrieval-adaptation-lab-docling\Scripts\python.exe scripts\run_document_intelligence.py `
  --data-root D:\AI-Lab\data\retrieval-adaptation-lab\ingestion_002 `
  --artifacts-path D:\AI-Lab\models\docling\2.111.0
```
