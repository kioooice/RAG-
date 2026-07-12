"""Export the existing 003/004 MX-100 units with traceability metadata.

This does not change ingestion or retrieval.  It reruns the existing 003
Docling adapter, applies the exact 004 accepted-document and content-dedup
rules, and writes a small reproducible metadata sidecar for iteration 006.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.docling_adapter import process_hybrid_directory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifacts-path", type=Path, required=True)
    args = parser.parse_args()

    records, units = process_hybrid_directory(args.input_dir, args.artifacts_path)
    accepted = {record["document_id"] for record in records if record["processing_status"] == "accepted"}
    filenames = {record["document_id"]: record["original_filename"] for record in records}
    candidates: list[dict] = []
    for unit in units:
        if unit["document_id"] not in accepted:
            continue
        content = unit["text"] or "\n".join(
            " | ".join(map(str, row)) for row in (unit.get("structured_data") or [])
        )
        if not content.strip():
            continue
        normalized = " ".join(content.split())
        candidates.append(
            {
                **unit,
                "text": normalized,
                "source_filename": filenames.get(unit["document_id"]),
                "source_relative_path": f"ingestion_002/input/{filenames.get(unit['document_id'])}",
            }
        )
    by_text: dict[str, dict] = {}
    for unit in candidates:
        current = by_text.get(unit["text"])
        if current is None or unit["unit_id"] < current["unit_id"]:
            by_text[unit["text"]] = unit
    selected = sorted(by_text.values(), key=lambda item: item["unit_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for unit in selected:
            handle.write(json.dumps(unit, ensure_ascii=False, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "accepted_source_units": len(candidates),
                "deduplicated_units": len(selected),
                "output": str(args.output),
                "rule": "same accepted-document and normalized-content dedup as prepare_mx100_retrieval_corpus.py",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
