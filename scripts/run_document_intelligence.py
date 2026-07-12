from __future__ import annotations

import argparse
import csv
import html
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.docling_adapter import process_hybrid_directory
from src.ingestion.pipeline import process_directory as process_002


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def text_for(units, document_id):
    selected = [unit for unit in units if unit["document_id"] == document_id]
    return "\n".join(
        unit["text"] + json.dumps(unit["structured_data"], ensure_ascii=False)
        for unit in selected
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--artifacts-path", type=Path, required=True)
    parser.add_argument(
        "--iteration-dir",
        type=Path,
        default=PROJECT_ROOT / "iterations/003_document_intelligence",
    )
    args = parser.parse_args()
    input_dir = args.data_root / "input"
    ground_truth = json.loads((args.data_root / "ground_truth.json").read_text(encoding="utf-8"))

    baseline_docs, baseline_units = process_002(input_dir)
    docs, units = process_hybrid_directory(input_dir, args.artifacts_path)
    docs_second, units_second = process_hybrid_directory(input_dir, args.artifacts_path)
    by_name = {doc["original_filename"]: doc for doc in docs}
    baseline_by_name = {doc["original_filename"]: doc for doc in baseline_docs}
    checks = []

    def check(name, passed, detail="", group="original_38"):
        checks.append({"name": name, "passed": bool(passed), "detail": detail, "group": group})

    expected_status = {
        name: ("accepted" if name in {"mx100_scanned.pdf", "mx100_image.png"} else expected["status"])
        for name, expected in ground_truth["files"].items()
    }
    for name, expected in ground_truth["files"].items():
        check(f"route:{name}", by_name[name]["detected_file_type"] == expected["type"])
        check(f"status:{name}", by_name[name]["processing_status"] == expected_status[name])
    all_text = "\n".join(
        unit["text"] + json.dumps(unit["structured_data"], ensure_ascii=False) for unit in units
    )
    for term in ground_truth["required_terms"]:
        check(f"preserve:{term}", term in all_text)
    for step in ground_truth["steps"]:
        check(f"step:{step}", step in all_text)
    check("deterministic_document_ids", [d["document_id"] for d in docs] == [d["document_id"] for d in docs_second])
    check("deterministic_unit_ids", [u["unit_id"] for u in units] == [u["unit_id"] for u in units_second])
    check("no_duplicate_units_second_run", len({u["unit_id"] for u in units_second}) == len(units_second))
    check("word_heading_trace", any(u["section_path"] for u in units if u["document_id"] == by_name["mx100_manual.docx"]["document_id"]))
    check("pdf_page_trace", any(u["source_locator"].get("page") == 1 for u in units if u["document_id"] == by_name["mx100_text.pdf"]["document_id"]))
    check("xlsx_sheet_range", any(u["source_locator"].get("sheet") and u["source_locator"].get("cell_range") for u in units if u["document_id"] == by_name["mx100_records.xlsx"]["document_id"]))
    check("ppt_slide_trace", any(u["source_locator"].get("slide") == 1 for u in units if u["document_id"] == by_name["mx100_brief.pptx"]["document_id"]))
    check("tables_structured", any(u["unit_type"] == "table" and u["structured_data"] for u in units))

    for filename in ("mx100_scanned.pdf", "mx100_image.png"):
        document = by_name[filename]
        content = text_for(units, document["document_id"])
        check(f"ocr:{filename}:meaningful_text", len(content.strip()) >= 40, str(len(content)), "ocr_extension")
        for term in ("MX-100", "75℃", "E07"):
            check(f"ocr:{filename}:preserve:{term}", term in content, group="ocr_extension")
        check(
            f"ocr:{filename}:region",
            any((u["source_locator"].get("bbox") or u["source_locator"].get("region")) for u in units if u["document_id"] == document["document_id"]),
            group="ocr_extension",
        )
        confidence = document["conversion_metrics"].get("confidence", {})
        check(
            f"ocr:{filename}:confidence_report",
            "ocr_score" in confidence,
            json.dumps(confidence, ensure_ascii=False),
            "ocr_extension",
        )

    original_checks = [item for item in checks if item["group"] == "original_38"]
    assert len(original_checks) == 38, f"Expected 38 retained checks, got {len(original_checks)}"

    improvements, regressions, unchanged = [], [], []
    for name in sorted(by_name):
        before = baseline_by_name[name]["processing_status"]
        after = by_name[name]["processing_status"]
        if before == "needs_ocr" and after == "accepted":
            improvements.append({"file": name, "before": before, "after": after, "reason": "OCR produced meaningful text"})
        elif before == after:
            unchanged.append({"file": name, "before": before, "after": after})
        else:
            regressions.append({"file": name, "before": before, "after": after})

    status_counts = dict(Counter(doc["processing_status"] for doc in docs))
    parser_counts = dict(Counter(doc["parser_name"] for doc in docs))
    timings = {
        doc["original_filename"]: doc["conversion_metrics"].get("seconds")
        for doc in docs if doc["parser_name"] == "docling"
    }
    peaks = {
        doc["original_filename"]: doc["conversion_metrics"].get("peak_rss_bytes")
        for doc in docs if doc["parser_name"] == "docling"
    }
    metrics = {
        "iteration": "003_document_intelligence",
        "rule_version": "document-intelligence-v0.1",
        "controlled_fixture_files": len(docs),
        "document_record_count": len(docs),
        "knowledge_unit_count": len(units),
        "status_counts": status_counts,
        "parser_counts": parser_counts,
        "retained_ground_truth": {
            "passed": sum(item["passed"] for item in original_checks),
            "total": len(original_checks),
            "checks": original_checks,
        },
        "ocr_extension": {
            "passed": sum(item["passed"] for item in checks if item["group"] == "ocr_extension"),
            "total": sum(item["group"] == "ocr_extension" for item in checks),
            "checks": [item for item in checks if item["group"] == "ocr_extension"],
        },
        "deterministic_second_run": all(item["passed"] for item in checks if item["name"].startswith(("deterministic", "no_duplicate"))),
        "timing_seconds_by_file": timings,
        "peak_rss_bytes_by_file": peaks,
        "comparison_to_002": {"improvements": improvements, "regressions": regressions, "unchanged": unchanged},
        "documents": docs,
        "representative_units": units[:15],
    }

    env_root = Path(sys.prefix)
    model_files = []
    for path in args.artifacts_path.rglob("*"):
        if path.is_file():
            model_files.append({"path": str(path.relative_to(args.artifacts_path)), "bytes": path.stat().st_size})
    resource = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "environment_path": str(env_root),
        "environment_bytes": directory_size(env_root),
        "artifacts_path": str(args.artifacts_path),
        "model_bytes": sum(item["bytes"] for item in model_files),
        "model_files": model_files,
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("docling", "docling-core", "docling-parse", "docling-ibm-models", "torch", "rapidocr", "onnxruntime")
        },
        "device": "cpu",
        "cuda_available": False,
        "peak_gpu_bytes": 0,
        "pip_check": subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True).stdout.strip(),
        "offline_repeat": metrics["deterministic_second_run"],
        "offline_mode_verified": os.environ.get("HF_HUB_OFFLINE") == "1" and os.environ.get("TRANSFORMERS_OFFLINE") == "1",
        "download_budget_estimate_bytes": {"python_packages": 337945499, "docling_models_repo": 358236338},
        "installation_incident": "Initial command timeout left child processes; a subsequent install hit WinError 32 until those scoped processes were stopped.",
    }

    args.iteration_dir.mkdir(parents=True, exist_ok=True)
    (args.iteration_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.iteration_dir / "resource_report.json").write_text(json.dumps(resource, ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.iteration_dir / "failures.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["file", "processing_status", "failure_stage", "error_or_warning", "retryable", "recommended_action"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for document in docs:
            if document["processing_status"] != "accepted" or document["warnings"]:
                writer.writerow({
                    "file": document["original_filename"],
                    "processing_status": document["processing_status"],
                    "failure_stage": "routing_or_conversion",
                    "error_or_warning": ";".join(document["warnings"]),
                    "retryable": document["processing_status"] in {"failed", "needs_review"},
                    "recommended_action": "manual review" if document["processing_status"] == "needs_review" else "keep unsupported/duplicate policy",
                })
        for item in checks:
            if not item["passed"]:
                writer.writerow({"file": "controlled_ground_truth", "processing_status": "failed", "failure_stage": item["name"], "error_or_warning": item["detail"], "retryable": True, "recommended_action": "inspect Docling output; do not weaken assertion"})

    rows = "".join(
        f"<tr><td>{html.escape(doc['original_filename'])}</td><td>{doc['detected_file_type']}</td><td>{doc['processing_status']}</td><td>{doc['parser_name']}</td><td>{sum(unit['document_id']==doc['document_id'] for unit in units)}</td><td>{doc['conversion_metrics'].get('seconds','')}</td><td>{html.escape('; '.join(doc['warnings']))}</td></tr>"
        for doc in docs
    )
    check_rows = "".join(
        f"<li class={'ok' if item['passed'] else 'bad'}>{'PASS' if item['passed'] else 'FAIL'} — {html.escape(item['name'])}</li>"
        for item in checks
    )
    page = f"""<!doctype html><meta charset=utf-8><title>003 Document Intelligence inspection</title>
<style>body{{font:15px system-ui;margin:36px;color:#18212b}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#17324d;color:white}}.ok{{color:#18794e}}.bad{{color:#b42318}}pre{{white-space:pre-wrap;background:#f5f6f7;padding:16px}}</style>
<h1>003 Document Intelligence 检查</h1><p>文件 {len(docs)} · KnowledgeUnit {len(units)} · 原 38 项 {sum(i['passed'] for i in original_checks)}/38 · OCR 扩展 {metrics['ocr_extension']['passed']}/{metrics['ocr_extension']['total']}</p>
<h2>文件路由与处理</h2><table><tr><th>文件</th><th>类型</th><th>状态</th><th>解析器</th><th>单元</th><th>秒</th><th>警告</th></tr>{rows}</table>
<h2>Ground Truth</h2><ul>{check_rows}</ul><h2>代表性统一知识单元</h2><pre>{html.escape(json.dumps(units[:5], ensure_ascii=False, indent=2))}</pre>"""
    (args.iteration_dir / "inspection.html").write_text(page, encoding="utf-8")
    print(json.dumps({key: metrics[key] for key in ("controlled_fixture_files", "knowledge_unit_count", "status_counts", "parser_counts", "retained_ground_truth", "ocr_extension", "deterministic_second_run", "comparison_to_002")}, ensure_ascii=False, indent=2))
    return 0 if all(item["passed"] for item in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
