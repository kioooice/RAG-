# 002 多格式资料接入基线结果

## 1. 文件如何识别

管线先检查PDF、PNG和ZIP文件签名；ZIP再检查Word、Excel或PowerPoint的Open XML目录。CSV、JSON和Markdown必须能按实际结构读取。扩展名仅用于期望类型，不能覆盖真实内容检测。

## 2. 格式路由

- DOCX -> python-docx，保留标题路径、段落和二维表格。
- 文本PDF -> pypdf，按页生成单元并保留页码。
- 扫描PDF -> pypdf检测无文本层，状态`needs_ocr`，不生成虚假文本。
- XLSX -> openpyxl只读解析，按工作表生成结构化表格并保留范围。
- PPTX -> 直接读取Open XML，按幻灯片保存正文和表格。
- CSV/JSON/Markdown -> 标准库解析；PNG -> `needs_ocr`；未知二进制 -> `unsupported`。

## 3. 统一内容

所有可处理内容转换为DocumentRecord与KnowledgeUnit。文字统一换行和空白但不改写；MX-100、75℃、E07、日期和中英文数字均保留。表格保存为二维数组，不拼成长文本。

## 4. 仍保留的格式差异

统一对象不抹平来源定位：PDF保留页码、Word保留段落和标题路径、Excel保留工作表与单元格范围、PPT保留幻灯片编号、CSV/JSON保留行范围或JSON路径。

## 5. 可以进入知识库的文件

7个`accepted`文件：DOCX、文本PDF、XLSX、PPTX、CSV、JSON和Markdown，共生成18个KnowledgeUnit。扩展名异常PDF虽然成功提取文字，但状态为`needs_review`，未经确认不能自动进入。

## 6. 不能直接进入的文件

扫描PDF和PNG共2个`needs_ocr`；1个重复Markdown为`duplicate`；未知二进制为`unsupported`；错误扩展名文件为`needs_review`。

## 7. 为什么扫描PDF不能假装成功

扫描页视觉上有文字，但PDF没有机器可读文本层。本轮没有OCR引擎或视觉模型，因此只能记录页数、文件和`needs_ocr`，不能把生成脚本变量或图片上的文字冒充解析结果。

## 8. 统一格式示例

```json
{
  "unit_id": "unit_<deterministic-hash>",
  "document_id": "doc_<sha256>",
  "unit_type": "table",
  "title": "故障处理",
  "structured_data": [["代码", "现象", "处理"], ["E07", "温度过高", "检查散热"]],
  "source_locator": {"sheet": "故障处理", "cell_range": "A1:C4"},
  "rule_version": "ingestion-rules-v0.1"
}
```

## 9. 测试结果

受控包包含12个文件，覆盖10条处理路线和重复/异常场景。Ground Truth 38/38通过；两次完整处理的Document ID和Unit ID一致，第二次没有新增重复KnowledgeUnit。

## 10. 失败与警告

最终没有`failed`文件。首次运行曾因artifact-tool生成的流式XLSX需要`calculate_dimension(force=True)`而失败，修正后通过。保留的非成功状态为2个`needs_ocr`、1个`needs_review`、1个`duplicate`和1个`unsupported`，详见`failures.csv`。

## 11. 当前边界

没有OCR、版面恢复、复杂合并单元格语义、公式计算、宏、密码文件、旧Office二进制格式或损坏文件恢复。PPT解析只覆盖Open XML文本和表格。DOCX因本机无LibreOffice未完成像素级渲染，但结构化回读通过。

## 12. 下一步假设

下一轮只值得验证一个假设：加入一个受控OCR引擎后，扫描PDF和PNG能否保留MX-100、75℃、E07及表格关系，同时提供区域坐标和可量化置信度；在此之前不应让图片资料进入可检索知识内容。
