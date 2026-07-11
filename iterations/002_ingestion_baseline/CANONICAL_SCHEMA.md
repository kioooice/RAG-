# 统一知识格式

`DocumentRecord`记录：`document_id, source_path, original_filename, detected_file_type, file_size, checksum, version, parser_name, parser_version, processing_status, quality_score, warnings, processed_at`。

`KnowledgeUnit`记录：`unit_id, document_id, unit_type, title, section_path, text, structured_data, source_locator, metadata, quality_score, parser_name, rule_version`。

`source_locator`按格式保存PDF页码、Word段落/标题路径、Excel工作表/范围、PPT幻灯片、CSV行范围、JSON字段路径、图片文件/区域。每个Unit必须持有DocumentRecord的`document_id`。
