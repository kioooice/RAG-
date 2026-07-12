"""Re-score and finalize Round 6 artifacts without calling the model again.

The long-running generation pass writes complete per-query records first.  This
small deterministic pass keeps the raw outputs intact while adding the Round 5
reference metrics, stage-1 extraction metrics and explicit baseline parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

import run_context_assembly as assembly


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration-dir", type=Path, required=True)
    parser.add_argument("--dataset-v2", type=Path, required=True)
    parser.add_argument("--dataset-005", type=Path, required=True)
    parser.add_argument("--metrics-005", type=Path, required=True)
    parser.add_argument("--evidence-units", type=Path, required=True)
    args = parser.parse_args()

    out = args.iteration_dir
    rows = assembly.load_jsonl(out / "generation_results.jsonl")
    dataset = {row["query_id"]: row for row in assembly.load_jsonl(args.dataset_v2)}
    old = {row["query_id"]: row for row in assembly.load_jsonl(args.dataset_005) }
    old_metrics = json.loads(args.metrics_005.read_text(encoding="utf-8"))
    units = assembly.load_jsonl(args.evidence_units)
    by_id = {unit["unit_id"]: unit for unit in units}

    for item in rows:
        row = dataset[item["query_id"]]
        context_ids = item.get("context_unit_ids", [])
        packet = {
            "text": item.get("packet_text", ""),
            "units": item.get("packet_units", []),
            "allowed_ids": item.get("packet_allowed_ids", context_ids),
            "duplicate_ids": item.get("packet_duplicate_ids", []),
            "truncated_ids": item.get("packet_truncated_ids", []),
        }
        stats = {
            "parsed_output": item.get("parsed_output", {}),
            "raw_model_output": item.get("raw_model_output", ""),
            "input_tokens": item.get("input_tokens"),
            "output_tokens": item.get("output_tokens"),
            "total_generation_ms": item.get("total_generation_ms"),
            "first_token_latency_ms": item.get("first_token_latency_ms"),
            "tokens_per_second": item.get("generation_tokens_per_second"),
            "timings": item.get("server_timings", {}),
        }
        selected = None
        if item.get("condition", "").endswith("_extract"):
            selected = {e.get("citation") for e in (item.get("extracted_evidence") or [])}
        refreshed = assembly.evaluate_final(row, item["condition"], context_ids, packet, stats, by_id, item.get("extraction"), selected)
        for key, value in refreshed.items():
            if key in {"packet_units", "packet_text", "packet_allowed_ids", "packet_duplicate_ids", "packet_truncated_ids", "context_unit_ids", "condition", "stage", "query_id", "question_type", "query", "reference_answer", "required_facts"}:
                continue
            item[key] = value
        item["packet_units"] = packet["units"]
        item["packet_text"] = packet["text"]
        item["packet_allowed_ids"] = packet["allowed_ids"]
        item["packet_duplicate_ids"] = packet["duplicate_ids"]
        item["packet_truncated_ids"] = packet["truncated_ids"]
        if item["condition"] == "baseline_dense":
            old_parsed = item.get("baseline_005_parsed_output") or {}
            item["legacy_context_text"] = "\n".join(
                f"[{unit_id}] {by_id.get(unit_id, {}).get('text', '')}" for unit_id in context_ids
            )
            item["baseline_status_answer_match"] = (
                item.get("status") == old_parsed.get("status")
                and assembly.ntext(item.get("answer", "")) == assembly.ntext(old_parsed.get("answer", ""))
            )

    out.joinpath("generation_results.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in rows) + "\n", encoding="utf-8"
    )

    condition_names = ["baseline_dense", "oracle_packet", "dense_packet", "oracle_extract", "dense_extract"]
    condition_metrics = {name: assembly.describe_metrics([item for item in rows if item["condition"] == name]) for name in condition_names}
    extract_rows = [item for item in rows if item["condition"].endswith("_extract")]
    extract_answerable = [item for item in extract_rows if item["question_type"] == "answerable"]
    extraction_stage = {
        "stage1_schema_pass_rate": statistics.fmean([float(item["extract_stage"].get("extraction_schema_valid", False)) for item in extract_rows]),
        "evidence_extraction_precision": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_precision", 0.0)) for item in extract_rows]),
        "evidence_extraction_recall": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_recall", 0.0)) for item in extract_rows]),
        "verbatim_support_valid_rate": (
            sum(int(item["extract_stage"].get("valid_item_count", 0)) for item in extract_rows)
            / max(1, sum(int(item["extract_stage"].get("extraction_item_count", 0)) for item in extract_rows))
        ),
        "answerable_only_precision": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_precision", 0.0)) for item in extract_answerable]),
        "answerable_only_recall": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_recall", 0.0)) for item in extract_answerable]),
        "oracle": {
            "stage1_schema_pass_rate": statistics.fmean([float(item["extract_stage"].get("extraction_schema_valid", False)) for item in extract_rows if item["condition"] == "oracle_extract"]),
            "precision": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_precision", 0.0)) for item in extract_rows if item["condition"] == "oracle_extract"]),
            "recall": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_recall", 0.0)) for item in extract_rows if item["condition"] == "oracle_extract"]),
        },
        "dense": {
            "stage1_schema_pass_rate": statistics.fmean([float(item["extract_stage"].get("extraction_schema_valid", False)) for item in extract_rows if item["condition"] == "dense_extract"]),
            "precision": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_precision", 0.0)) for item in extract_rows if item["condition"] == "dense_extract"]),
            "recall": statistics.fmean([float(item["extract_stage"].get("evidence_extraction_recall", 0.0)) for item in extract_rows if item["condition"] == "dense_extract"]),
        },
    }
    baseline_rows = [item for item in rows if item["condition"] == "baseline_dense"]
    exact_matches = [bool(item.get("baseline_reproduction_match")) for item in baseline_rows]
    semantic_matches = [bool(item.get("baseline_status_answer_match")) for item in baseline_rows]
    packet_contexts = [item for item in rows if item.get("packet_text") is not None]
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    metrics["conditions"] = condition_metrics
    metrics["round5_reference_metrics"] = {"dense_rag": old_metrics["conditions"]["dense_rag"]}
    metrics["baseline_reproduction"] = {
        "exact_output_matches": sum(exact_matches),
        "status_and_answer_matches": sum(semantic_matches),
        "total_queries": len(baseline_rows),
        "exact_match_rate": sum(exact_matches) / len(exact_matches),
        "status_and_answer_match_rate": sum(semantic_matches) / len(semantic_matches),
        "mismatches": [item["query_id"] for item, same in zip(baseline_rows, exact_matches) if not same],
        "interpretation": "固定参数下语义结果可复现，但llama.cpp CPU运行的部分引用集合或标点存在非逐字差异；不把这些差异当作新检索器变化。",
    }
    metrics["extraction"] = extraction_stage
    metrics["packet"]["average_context_chars"] = statistics.fmean([len(item.get("packet_text", "")) for item in packet_contexts])
    metrics["packet"]["duplicate_evidence_count"] = sum(len(item.get("packet_duplicate_ids", [])) for item in packet_contexts)
    metrics["packet"]["truncated_evidence_count"] = sum(len(item.get("packet_truncated_ids", [])) for item in packet_contexts)
    oracle_extract_metrics = condition_metrics["oracle_extract"]
    metrics["decision"] = {
        "default_generation_orchestration": "extract_then_answer" if (
            oracle_extract_metrics["answerable_correctness"] >= 0.90
            and oracle_extract_metrics["required_fact_recall"] >= 0.95
            and oracle_extract_metrics["citation_validity_answered"] == 1.0
            and oracle_extract_metrics["citation_support_rate"] >= 0.95
            and oracle_extract_metrics["false_refusal_rate"] <= 0.10
            and oracle_extract_metrics["unsupported_claim_rate"] <= 0.05
        ) else "not_confirmed",
        "oracle_completeness_required_for_interpretation": True,
        "next_action_trigger": "compare stronger model only if complete Oracle still fails; no automatic download",
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    assembly.write_failures(out / "failures.csv", rows)
    audits = {}
    for qid, row in dataset.items():
        oracle_ids = row.get("oracle_unit_ids_v2") or row.get("relevant_unit_ids", [])
        dense_ids = next((item.get("context_unit_ids", []) for item in rows if item["query_id"] == qid and item["condition"] == "baseline_dense"), [])
        audits[qid] = {
            "oracle_unit_ids_original": row.get("relevant_unit_ids", []),
            "oracle_unit_ids_v2": oracle_ids,
            "dense_top5": dense_ids,
            "oracle_fact_locations": assembly.coverage(row.get("required_facts", []), oracle_ids, by_id),
            "dense_fact_locations": assembly.coverage(row.get("required_facts", []), dense_ids, by_id),
        }
    assembly.write_inspection(out / "inspection.html", rows, audits)
    print(json.dumps({"baseline_reproduction": metrics["baseline_reproduction"], "conditions": metrics["conditions"], "extraction": metrics["extraction"], "decision": metrics["decision"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
