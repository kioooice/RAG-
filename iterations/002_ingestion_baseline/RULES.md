# 资料接入规则 ingestion-rules-v0.1

- 识别：先检查PDF/PNG/ZIP签名；ZIP内检查`word/`、`xl/`、`ppt/`结构；文本格式需通过实际解析。扩展名与真实类型不一致进入`needs_review`。
- 路由：DOCX、文本PDF、XLSX、PPTX、CSV、JSON、Markdown进入对应解析器；PNG及无文字PDF进入`needs_ocr`；其他进入`unsupported`。
- 清洗：删除空白内容、统一LF和行内空白；保留数字、单位、E07等代码；不改写原文；表格保留二维数组。
- 去重：先文件SHA-256，再规范化内容SHA-256；ID由内容确定，相同输入重复运行不新增ID。
- 状态：`accepted`、`accepted_with_warnings`、`needs_ocr`、`needs_review`、`unsupported`、`failed`、`duplicate`。
