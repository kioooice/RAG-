"""Docling adapter that preserves the existing canonical ingestion schema."""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import time
from pathlib import Path
from typing import Any

import psutil

from src.ingestion.pipeline import (
    detect,
    norm,
    parse_csv_file,
    parse_json_file,
    parse_markdown,
    sha,
)

RULE_VERSION = "document-intelligence-v0.1"
DOCLING_TYPES = {"pdf", "png", "docx", "pptx", "xlsx"}
SIMPLE_TYPES = {"csv", "json", "markdown"}


def _safe_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _stable_unit(
    doc_id: str,
    kind: str,
    title: str,
    text: str,
    locator: dict[str, Any],
    structured: Any = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean = norm(text)
    key = json.dumps(
        [doc_id, kind, title, locator, clean, structured],
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return {
        "unit_id": "unit_" + hashlib.sha256(key).hexdigest()[:20],
        "document_id": doc_id,
        "unit_type": kind,
        "title": title,
        "section_path": list((metadata or {}).get("section_path", [])),
        "text": clean,
        "structured_data": structured,
        "source_locator": locator,
        "metadata": metadata or {},
        "quality_score": 1.0 if clean or structured else 0.0,
        "parser_name": "docling",
        "rule_version": RULE_VERSION,
    }


def _table_grid(item: dict[str, Any]) -> list[list[str]]:
    data = item.get("data") or {}
    rows, cols = int(data.get("num_rows", 0)), int(data.get("num_cols", 0))
    grid = [["" for _ in range(cols)] for _ in range(rows)]
    for cell in data.get("table_cells", []):
        row = int(cell.get("start_row_offset_idx", 0))
        col = int(cell.get("start_col_offset_idx", 0))
        if 0 <= row < rows and 0 <= col < cols:
            grid[row][col] = norm(str(cell.get("text", "")))
    return grid


def _excel_col(number: int) -> str:
    value, out = max(number, 1), ""
    while value:
        value, rem = divmod(value - 1, 26)
        out = chr(65 + rem) + out
    return out


def _parent_group(item: dict[str, Any], index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    ref = (item.get("parent") or {}).get("$ref")
    while ref:
        parent = index.get(ref)
        if not parent:
            return None
        if ref.startswith("#/groups/"):
            return parent
        ref = (parent.get("parent") or {}).get("$ref")
    return None


def _locator(
    item: dict[str, Any], file_type: str, filename: str, index: dict[str, dict[str, Any]], item_no: int
) -> dict[str, Any]:
    prov = (item.get("prov") or [{}])[0]
    bbox = prov.get("bbox")
    page = prov.get("page_no")
    locator: dict[str, Any] = {"item_ref": item.get("self_ref")}
    if file_type == "pdf":
        locator.update(page=page, bbox=bbox)
    elif file_type == "png":
        locator.update(file=filename, page=page, region=bbox)
    elif file_type == "pptx":
        locator.update(slide=page, bbox=bbox)
    elif file_type == "xlsx":
        group = _parent_group(item, index)
        locator["sheet"] = (group or {}).get("name")
        if bbox:
            # Docling's spreadsheet backend exposes zero-based column/row bounds.
            first_col = int(float(bbox.get("l", 0))) + 1
            last_col = int(float(bbox.get("r", first_col)))
            first_row = int(float(bbox.get("t", 0))) + 1
            last_row = int(float(bbox.get("b", first_row)))
            locator["cell_range"] = f"{_excel_col(first_col)}{first_row}:{_excel_col(last_col)}{last_row}"
    elif file_type == "docx":
        locator["paragraph_or_table"] = item_no
    return locator


def docling_dict_to_units(
    exported: dict[str, Any], doc_id: str, file_type: str, filename: str
) -> list[dict[str, Any]]:
    """Convert lossless Docling JSON to stable KnowledgeUnit dictionaries."""
    index: dict[str, dict[str, Any]] = {}
    for collection in ("groups", "texts", "tables", "pictures", "key_value_items", "form_items"):
        for item in exported.get(collection, []):
            if item.get("self_ref"):
                index[item["self_ref"]] = item

    ordered: list[dict[str, Any]] = []
    visited: set[str] = set()

    def walk(ref: str) -> None:
        if ref in visited:
            return
        visited.add(ref)
        item = index.get(ref)
        if not item:
            return
        if ref.startswith(("#/texts/", "#/tables/")):
            ordered.append(item)
        for child in item.get("children", []):
            walk(child.get("$ref", ""))

    for child in (exported.get("body") or {}).get("children", []):
        walk(child.get("$ref", ""))
    for item in list(exported.get("texts", [])) + list(exported.get("tables", [])):
        if item.get("self_ref") not in visited:
            ordered.append(item)

    units: list[dict[str, Any]] = []
    section_path: list[str] = []
    for item_no, item in enumerate(ordered, 1):
        label = str(item.get("label", "text"))
        text = norm(str(item.get("text", "")))
        if label in {"title", "section_header"} and text:
            if label == "title":
                section_path = [text]
            else:
                section_path = section_path[:1] + [text]
        locator = _locator(item, file_type, filename, index, item_no)
        metadata = {
            "docling_label": label,
            "section_path": section_path.copy(),
            "reading_order": item_no,
        }
        if label == "table":
            grid = _table_grid(item)
            table_text = "\n".join(" | ".join(row) for row in grid)
            units.append(_stable_unit(doc_id, "table", f"Table {item_no}", table_text, locator, grid, metadata))
        elif text:
            units.append(_stable_unit(doc_id, label, text if label in {"title", "section_header"} else filename, text, locator, metadata=metadata))
    return units


class _MemorySampler:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self.peak = 0

    def __enter__(self) -> "_MemorySampler":
        process = psutil.Process()
        self.peak = process.memory_info().rss

        def sample() -> None:
            while not self._stop.wait(0.02):
                rss = process.memory_info().rss
                for child in process.children(recursive=True):
                    try:
                        rss += child.memory_info().rss
                    except psutil.Error:
                        pass
                self.peak = max(self.peak, rss)

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self._stop.set()
        self.thread.join(timeout=1)


class DoclingAdapter:
    def __init__(self, artifacts_path: Path) -> None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption

        options = PdfPipelineOptions(
            artifacts_path=artifacts_path,
            do_ocr=True,
            do_table_structure=True,
            ocr_options=RapidOcrOptions(lang=["chinese"], text_score=0.5),
        )
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
            }
        )

    def convert(self, path: Path, doc_id: str, file_type: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        started = time.perf_counter()
        with _MemorySampler() as memory:
            result = self.converter.convert(path, raises_on_error=False)
        elapsed = time.perf_counter() - started
        status = str(result.status).split(".")[-1].lower()
        exported = result.document.export_to_dict() if result.document else {}
        units = docling_dict_to_units(exported, doc_id, file_type, path.name)
        confidence = result.confidence.model_dump(mode="json")
        metrics = {
            "conversion_status": status,
            "seconds": elapsed,
            "peak_rss_bytes": memory.peak,
            "confidence": {
                key: _safe_number(confidence.get(key))
                for key in ("parse_score", "layout_score", "table_score", "ocr_score", "mean_score", "low_score")
            },
            "errors": [str(error) for error in result.errors],
        }
        return units, metrics


def _has_meaningful_content(units: list[dict[str, Any]]) -> bool:
    text = " ".join(unit["text"] for unit in units)
    text += " " + json.dumps([unit["structured_data"] for unit in units], ensure_ascii=False)
    useful = re.findall(r"[A-Za-z0-9\u3400-\u9fff]", text)
    return len(useful) >= 4 and text.count("�") <= max(1, len(text) // 100)


def process_hybrid_directory(input_dir: Path, artifacts_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Use Docling for complex formats and existing deterministic parsers for simple formats."""
    adapter = DoclingAdapter(artifacts_path)
    seen_file: dict[str, str] = {}
    seen_content: dict[str, str] = {}
    documents: list[dict[str, Any]] = []
    units: list[dict[str, Any]] = []
    for path in sorted(input_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        checksum = sha(raw)
        file_type, mismatch = detect(path)
        doc_id = "doc_" + checksum[:20]
        warnings: list[str] = []
        parser_name = "docling" if file_type in DOCLING_TYPES else file_type
        conversion: dict[str, Any] = {}
        parsed: list[dict[str, Any]] = []
        status = "accepted"
        if checksum in seen_file:
            status = "duplicate"
            warnings.append(f"duplicate_of:{seen_file[checksum]}")
        else:
            seen_file[checksum] = path.name
            try:
                if file_type in DOCLING_TYPES:
                    parsed, conversion = adapter.convert(path, doc_id, file_type)
                    if conversion["conversion_status"] != "success":
                        status = "failed"
                        warnings.extend(conversion["errors"] or ["docling_conversion_failed"])
                    elif not _has_meaningful_content(parsed):
                        status = "needs_review"
                        warnings.append("empty_or_low_quality_docling_output")
                    else:
                        low_score = conversion.get("confidence", {}).get("low_score")
                        if low_score is not None and low_score < 0.5:
                            status = "accepted_with_warnings"
                            warnings.append(f"low_docling_confidence:{low_score:.3f}")
                elif file_type == "csv":
                    parsed = parse_csv_file(path, doc_id)
                elif file_type == "json":
                    parsed = parse_json_file(path, doc_id)
                elif file_type == "markdown":
                    parsed = parse_markdown(path, doc_id)
                else:
                    status = "unsupported"
                    warnings.append("unsupported_file_type")
                if mismatch:
                    status = "needs_review" if status == "accepted" else status
                    warnings.append("extension_content_mismatch")
                content_hash = sha(
                    "\n".join(
                        unit["text"] + json.dumps(unit["structured_data"], ensure_ascii=False, sort_keys=True)
                        for unit in parsed
                    ).encode("utf-8")
                ) if parsed else None
                if content_hash and content_hash in seen_content:
                    status = "duplicate"
                    warnings.append(f"content_duplicate_of:{seen_content[content_hash]}")
                    parsed = []
                elif content_hash:
                    seen_content[content_hash] = path.name
            except Exception as error:  # surfaced in the report; never accepted silently
                status = "failed"
                warnings.append(f"{type(error).__name__}:{error}")
        if file_type in {"png"} or (file_type == "pdf" and "scanned" in path.stem):
            conversion["ocr_expected"] = True
        quality = 1.0 if status == "accepted" else 0.8 if status in {"accepted_with_warnings", "needs_review"} else 0.0
        documents.append({
            "document_id": doc_id,
            "source_path": str(path),
            "original_filename": path.name,
            "detected_file_type": file_type,
            "file_size": len(raw),
            "checksum": checksum,
            "version": "v1.2",
            "parser_name": parser_name,
            "parser_version": "2.111.0" if parser_name == "docling" else "002-baseline",
            "processing_status": status,
            "quality_score": quality,
            "warnings": warnings,
            "processed_at": "deterministic",
            "conversion_metrics": conversion,
        })
        units.extend(parsed)
    return documents, units
