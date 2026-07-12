"""Export accepted 003 KnowledgeUnits to local JSONL for iteration 004."""
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
    parser.add_argument("--artifacts-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records, units = process_hybrid_directory(args.input_dir, args.artifacts_path)
    accepted = {record["document_id"] for record in records if record["processing_status"] == "accepted"}
    rows = []
    for unit in units:
        if unit["document_id"] not in accepted:
            continue
        text = unit["text"] or "\n".join(" | ".join(map(str, row)) for row in (unit["structured_data"] or []))
        if text.strip():
            rows.append({"document_id": unit["unit_id"], "text": text})
    by_text = {}
    for row in rows:
        text = " ".join(row["text"].split())
        candidate = {"document_id": row["document_id"], "text": text}
        current = by_text.get(text)
        if current is None or candidate["document_id"] < current["document_id"]:
            by_text[text] = candidate
    documents = sorted(by_text.values(), key=lambda item: item["document_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for document in documents:
            handle.write(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"accepted_source_units": len(rows), "deduplicated_documents": len(documents), "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
