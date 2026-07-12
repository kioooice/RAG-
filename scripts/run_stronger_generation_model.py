"""Round 7: compare Qwen3.5-9B Q4_K_M with the locked Round 6 results.

The script deliberately consumes the already materialized Round 6 Evidence
Packets and Dense Top-5 IDs.  It does not rebuild retrieval, change prompts,
or run Extract-then-Answer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import run_context_assembly as assembly


MODEL_ID = "Qwen/Qwen3.5-9B"
MODEL_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
MODEL_LICENSE = "Apache-2.0"
GGUF_REPO = "unsloth/Qwen3.5-9B-GGUF"
GGUF_REVISION = "3885219b6810b007914f3a7950a8d1b469d598a5"
GGUF_FILE = "Qwen3.5-9B-Q4_K_M.gguf"
GGUF_SIZE = 5680522464
GGUF_SHA256 = "03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8"
LLAMA_RELEASE = "b9968"
SEED = 42
MAX_TOKENS = 256
CONTEXT_SIZE = 8192
SMOKE_QUERY_IDS = ("mxq-001", "mxq-002", "mxq-022")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class Qwen35Server:
    def __init__(self, executable: Path, model: Path, work_dir: Path, port: int) -> None:
        self.executable = executable
        self.model = model
        self.work_dir = work_dir
        self.port = port
        self.process: subprocess.Popen[str] | None = None
        self.stdout_path = work_dir / "server.stdout.log"
        self.stderr_path = work_dir / "server.stderr.log"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> dict[str, Any]:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.stdout_path, self.stderr_path):
            path.unlink(missing_ok=True)
        args = [
            str(self.executable),
            "-m", str(self.model),
            "-c", str(CONTEXT_SIZE),
            "-np", "1",
            "-ngl", "0",
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--no-webui",
            "--offline",
            "--temp", "0",
            "--top-k", "1",
            "--seed", str(SEED),
            "-n", str(MAX_TOKENS),
            "--reasoning", "off",
            "--chat-template-kwargs", json.dumps({"enable_thinking": False}),
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self.stdout_path.open("w", encoding="utf-8") as stdout, self.stderr_path.open("w", encoding="utf-8") as stderr:
            self.process = subprocess.Popen(
                args, cwd=str(self.executable.parent), stdout=stdout, stderr=stderr,
                text=True, creationflags=creationflags,
            )
        health_url = self.url + "/health"
        for _ in range(240):
            if self.process.poll() is not None:
                error = self.stderr_path.read_text(encoding="utf-8", errors="replace")
                raise RuntimeError(f"llama-server exited with {self.process.returncode}: {error[-3000:]}")
            try:
                health = assembly.baseline.get_json(health_url, timeout=2)
                if health.get("status") == "ok":
                    break
            except Exception:
                pass
            time.sleep(2)
        else:
            error = self.stderr_path.read_text(encoding="utf-8", errors="replace")
            raise TimeoutError(f"llama-server did not become healthy: {error[-3000:]}")
        return {"url": self.url, "pid": self.process.pid, "stderr": str(self.stderr_path), "args": args}

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)


class ResourceSampler:
    def __init__(self, server_pid: int | None) -> None:
        self.server_pid = server_pid
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.peak_evaluator_rss = 0
        self.peak_server_rss = 0
        self.peak_total_rss = 0
        self.peak_gpu_mib = 0
        self.pagefile_before = psutil.swap_memory().used
        self.peak_pagefile_used = self.pagefile_before

    @staticmethod
    def gpu_mib() -> int:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            values = [int(v.strip()) for v in result.stdout.splitlines() if v.strip().isdigit()]
            return max(values, default=0)
        except Exception:
            return 0

    def __enter__(self) -> "ResourceSampler":
        evaluator = psutil.Process()
        self.peak_evaluator_rss = evaluator.memory_info().rss
        self.peak_gpu_mib = self.gpu_mib()

        def sample() -> None:
            while not self.stop_event.wait(0.25):
                try:
                    evaluator_rss = evaluator.memory_info().rss
                    server_rss = 0
                    if self.server_pid:
                        server = psutil.Process(self.server_pid)
                        if server.is_running():
                            server_rss = server.memory_info().rss
                    self.peak_evaluator_rss = max(self.peak_evaluator_rss, evaluator_rss)
                    self.peak_server_rss = max(self.peak_server_rss, server_rss)
                    self.peak_total_rss = max(self.peak_total_rss, evaluator_rss + server_rss)
                    self.peak_gpu_mib = max(self.peak_gpu_mib, self.gpu_mib())
                    self.peak_pagefile_used = max(self.peak_pagefile_used, psutil.swap_memory().used)
                except (psutil.Error, OSError):
                    continue

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)


def response_details(response: dict[str, Any]) -> dict[str, Any]:
    details = assembly.response_stats(response)
    message = ((response.get("choices") or [{}])[0].get("message") or {})
    reasoning = str(message.get("reasoning_content") or "")
    content = details["raw_model_output"]
    details.update(
        {
            "reasoning_content": reasoning,
            "think_tag_detected": "<think>" in content.lower() or "</think>" in content.lower() or "<think>" in reasoning.lower(),
            "response_id": response.get("id"),
            "system_fingerprint": response.get("system_fingerprint"),
        }
    )
    return details


def packet_from_006(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": item.get("packet_text", ""),
        "units": item.get("packet_units", []),
        "allowed_ids": item.get("packet_allowed_ids", item.get("context_unit_ids", [])),
        "duplicate_ids": item.get("packet_duplicate_ids", []),
        "truncated_ids": item.get("packet_truncated_ids", []),
    }


def evaluate_model_row(
    row: dict[str, Any],
    condition: str,
    context_ids: list[str],
    packet: dict[str, Any],
    details: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = assembly.evaluate_final(row, condition, context_ids, packet, details, by_id)
    result.update(
        {
            "model": "qwen3.5-9b-q4_k_m",
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "evaluation_phase": "formal",
            "reasoning_content": details.get("reasoning_content", ""),
            "think_tag_detected": details.get("think_tag_detected", False),
            "response_id": details.get("response_id"),
            "system_fingerprint": details.get("system_fingerprint"),
        }
    )
    return result


def run_smoke(args: argparse.Namespace, rows: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> int:
    smoke_rows = [row for row in rows if row["query_id"] in SMOKE_QUERY_IDS]
    fixed = {(item["condition"], item["query_id"]): item for item in assembly.load_jsonl(args.generation_006)}
    out = args.iteration_dir
    server = Qwen35Server(args.llama_server, args.model_path, args.runtime_dir, args.port)
    all_results: list[dict[str, Any]] = []
    server_meta: dict[str, Any] = {}
    sampler: ResourceSampler | None = None
    error: str | None = None
    try:
        server_meta = server.start()
        sampler = ResourceSampler(server.process.pid if server.process else None)
        sampler.__enter__()
        for repeat in range(1, 4):
            for row in smoke_rows:
                for condition in ("oracle_packet", "dense_packet"):
                    fixed_item = fixed[(condition, row["query_id"])]
                    packet = packet_from_006(fixed_item)
                    response = assembly.request_generation(
                        server.url, assembly.PACKET_SYSTEM_PROMPT,
                        assembly.packet_user(row["query"], packet["text"]), args.model_path,
                    )
                    details = response_details(response)
                    checked = assembly.validate_final(details["parsed_output"], set(fixed_item.get("context_unit_ids", [])), allow_used_facts=True)
                    all_results.append(
                        {
                            "repeat": repeat,
                            "query_id": row["query_id"],
                            "condition": condition,
                            "query": row["query"],
                            "raw_model_output": details["raw_model_output"],
                            "parsed_output": details["parsed_output"],
                            "schema_valid": checked["schema_valid"],
                            "citation_valid": checked["citation_valid"],
                            "think_tag_detected": details["think_tag_detected"],
                            "reasoning_content": details["reasoning_content"],
                            "total_generation_ms": details["total_generation_ms"],
                            "input_tokens": details.get("input_tokens"),
                            "output_tokens": details.get("output_tokens"),
                        }
                    )
    except Exception as exc:
        error = str(exc)
    finally:
        if sampler:
            sampler.__exit__(None, None, None)
        server.stop()

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in all_results:
        groups.setdefault((item["condition"], item["query_id"]), []).append(item)
    stable_groups = {
        f"{condition}:{qid}": len({stable_hash(item["parsed_output"]) for item in values}) == 1
        for (condition, qid), values in groups.items()
    }
    no_think = all(not item["think_tag_detected"] and not item["reasoning_content"] for item in all_results)
    schema_ok = all(item["schema_valid"] for item in all_results)
    citations_ok = all(item["citation_valid"] for item in all_results)
    stable = bool(stable_groups) and all(stable_groups.values())
    passed = not error and len(all_results) == 18 and no_think and schema_ok and citations_ok and stable
    stderr = ""
    if server.stderr_path.exists():
        stderr = server.stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
    report = {
        "phase": "smoke",
        "passed": passed,
        "error": error,
        "query_ids": list(SMOKE_QUERY_IDS),
        "repeats": 3,
        "result_count": len(all_results),
        "stable_groups": stable_groups,
        "no_think_tags_or_reasoning_content": no_think,
        "schema_valid_all": schema_ok,
        "citation_valid_all": citations_ok,
        "server": server_meta,
        "server_stderr_tail": stderr,
        "resources": {
            "peak_evaluator_rss_bytes": sampler.peak_evaluator_rss if sampler else None,
            "peak_server_rss_bytes": sampler.peak_server_rss if sampler else None,
            "peak_total_rss_bytes": sampler.peak_total_rss if sampler else None,
            "peak_gpu_memory_mib": sampler.peak_gpu_mib if sampler else None,
            "pagefile_before_bytes": sampler.pagefile_before if sampler else None,
            "pagefile_peak_used_bytes": sampler.peak_pagefile_used if sampler else None,
        },
        "results": all_results,
    }
    (out / "smoke_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "smoke_results.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in all_results) + ("\n" if all_results else ""),
        encoding="utf-8",
    )
    print(json.dumps({"passed": passed, "result_count": len(all_results), "stable": stable, "no_think": no_think, "schema": schema_ok, "citations": citations_ok}, ensure_ascii=False, indent=2))
    return 0 if passed else 2


def compare_rows(
    model_rows: list[dict[str, Any]], baseline_rows: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in model_rows:
        base = baseline_rows[(item["condition"].replace("_9b", ""), item["query_id"])]
        base_correct = bool(base.get("answer_correct"))
        model_correct = bool(item.get("answer_correct"))
        if model_correct and not base_correct:
            change = "improved"
        elif base_correct and not model_correct:
            change = "declined"
        else:
            change = "unchanged"
        output.append(
            {
                "query_id": item["query_id"],
                "condition": item["condition"],
                "query": item["query"],
                "question_type": item["question_type"],
                "four_b_answer_correct": base_correct,
                "nine_b_answer_correct": model_correct,
                "four_b_status": base.get("status"),
                "nine_b_status": item.get("status"),
                "four_b_required_fact_recall": base.get("required_fact_recall"),
                "nine_b_required_fact_recall": item.get("required_fact_recall"),
                "four_b_citation_valid": base.get("citation_valid"),
                "nine_b_citation_valid": item.get("citation_valid"),
                "four_b_citation_coverage": base.get("citation_coverage"),
                "nine_b_citation_coverage": item.get("citation_coverage"),
                "four_b_unsupported_claim": base.get("unsupported_claim"),
                "nine_b_unsupported_claim": item.get("unsupported_claim"),
                "change": change,
                "four_b_error_nine_b_correct": bool(not base_correct and model_correct),
                "both_error": bool(not base_correct and not model_correct),
                "new_hallucination": bool(item.get("unsupported_claim") and not base.get("unsupported_claim")),
                "new_citation_error": bool(not item.get("citation_valid") and base.get("citation_valid")),
                "four_b_answer": base.get("answer", ""),
                "nine_b_answer": item.get("answer", ""),
                "four_b_citations": "|".join(base.get("citations", [])),
                "nine_b_citations": "|".join(item.get("citations", [])),
            }
        )
    return output


def write_comparison(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["query_id", "condition"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_inspection(path: Path, model_rows: list[dict[str, Any]], comparison: list[dict[str, Any]], baseline_rows: dict[tuple[str, str], dict[str, Any]]) -> None:
    comparison_map = {(item["condition"], item["query_id"]): item for item in comparison}
    trs: list[str] = []
    for item in model_rows:
        cmp = comparison_map[(item["condition"], item["query_id"])]
        base = baseline_rows[(item["condition"].replace("_9b", ""), item["query_id"])]
        trs.append(
            "<tr data-condition='{condition}' data-type='{qtype}' data-change='{change}' data-correct='{correct}' data-failure='{failure}'>"
            "<td>{condition}</td><td>{qtype}</td><td>{change}</td><td>{correct}</td><td>{failure}</td><td>{query}</td>"
            "<td><details><summary>4B基线</summary><pre>{base}</pre></details></td>"
            "<td><details><summary>9B结果与Packet</summary><pre>{nine}</pre></details></td>"
            "<td><details><summary>对比</summary><pre>{cmp}</pre></details></td></tr>".format(
                condition=html.escape(item["condition"]),
                qtype=html.escape(item["question_type"]),
                change=html.escape(cmp["change"]),
                correct=str(item["answer_correct"]).lower(),
                failure=html.escape("|".join(item.get("failure_types", [])) or "none"),
                query=html.escape(item["query"]),
                base=html.escape(json.dumps({"answer": base.get("answer"), "status": base.get("status"), "citations": base.get("citations"), "required_fact_recall": base.get("required_fact_recall"), "citation_coverage": base.get("citation_coverage")}, ensure_ascii=False, indent=2)),
                nine=html.escape(json.dumps({"answer": item.get("answer"), "status": item.get("status"), "citations": item.get("citations"), "required_fact_recall": item.get("required_fact_recall"), "citation_coverage": item.get("citation_coverage"), "packet": item.get("packet_text")}, ensure_ascii=False, indent=2)),
                cmp=html.escape(json.dumps(cmp, ensure_ascii=False, indent=2)),
            )
        )
    page = """<!doctype html><meta charset=utf-8><title>007 stronger generation model</title>
<style>body{font:14px system-ui;margin:24px}select{margin:4px;padding:5px}table{border-collapse:collapse;width:100%}th,td{padding:7px;border-bottom:1px solid #ddd;vertical-align:top}th{position:sticky;top:0;background:#17324d;color:#fff}pre{white-space:pre-wrap;max-width:620px;max-height:360px;overflow:auto}details{max-width:650px}</style>
<h1>007 Qwen3.5-9B Q4_K_M 对照</h1><p>只运行 Oracle Packet / Dense Packet；4B结果来自006固定记录，9B使用完全相同的Packet、Prompt、Top-K和生成参数。</p>
<div><select data-k=condition><option value=''>全部条件</option><option>oracle_packet_9b</option><option>dense_packet_9b</option></select><select data-k=type><option value=''>全部问题</option><option>answerable</option><option>unanswerable</option></select><select data-k=change><option value=''>全部变化</option><option>improved</option><option>declined</option><option>unchanged</option></select><select data-k=correct><option value=''>全部正确性</option><option value='true'>正确</option><option value='false'>错误</option></select></div>
<table><thead><tr><th>条件</th><th>类型</th><th>变化</th><th>9B正确</th><th>失败</th><th>Query</th><th>4B基线</th><th>9B结果/Packet</th><th>差异</th></tr></thead><tbody>""" + "".join(trs) + """</tbody></table>
<script>const ss=[...document.querySelectorAll('select')],rs=[...document.querySelectorAll('tbody tr')];function f(){rs.forEach(r=>r.hidden=ss.some(s=>s.value&&r.dataset[s.dataset.k]!==s.value))}ss.forEach(s=>s.onchange=f)</script>"""
    path.write_text(page, encoding="utf-8")


def run_formal(args: argparse.Namespace, rows: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> int:
    out = args.iteration_dir
    smoke_path = out / "smoke_report.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.exists() else {}
    if not smoke.get("passed"):
        raise RuntimeError("Smoke test is missing or failed; formal evaluation is blocked")
    fixed006 = assembly.load_jsonl(args.generation_006)
    fixed = {(item["condition"], item["query_id"]): item for item in fixed006}
    baseline_rows = {key: value for key, value in fixed.items() if key[0] in {"oracle_packet", "dense_packet"}}
    server = Qwen35Server(args.llama_server, args.model_path, args.runtime_dir, args.port)
    sampler: ResourceSampler | None = None
    model_rows: list[dict[str, Any]] = []
    server_meta: dict[str, Any] = {}
    formal_error: str | None = None
    try:
        server_meta = server.start()
        sampler = ResourceSampler(server.process.pid if server.process else None)
        sampler.__enter__()
        for row in rows:
            qid = row["query_id"]
            for old_condition, new_condition in (("oracle_packet", "oracle_packet_9b"), ("dense_packet", "dense_packet_9b")):
                fixed_item = fixed[(old_condition, qid)]
                packet = packet_from_006(fixed_item)
                response = assembly.request_generation(
                    server.url, assembly.PACKET_SYSTEM_PROMPT,
                    assembly.packet_user(row["query"], packet["text"]), args.model_path,
                )
                details = response_details(response)
                result = evaluate_model_row(row, new_condition, list(fixed_item.get("context_unit_ids", [])), packet, details, by_id)
                result["fixed_006_packet_sha256"] = stable_hash(packet["text"])
                result["fixed_006_context_unit_ids"] = fixed_item.get("context_unit_ids", [])
                model_rows.append(result)
    except Exception as exc:
        formal_error = str(exc)
    finally:
        if sampler:
            sampler.__exit__(None, None, None)
        server.stop()
    if formal_error:
        (out / "resource_report.json").write_text(json.dumps({"formal_error": formal_error, "smoke": smoke}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(formal_error)

    (out / "generation_results.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in model_rows) + "\n", encoding="utf-8"
    )
    comparison = compare_rows(model_rows, baseline_rows)
    write_comparison(out / "model_comparison.csv", comparison)
    assembly.write_failures(out / "failures.csv", model_rows)
    write_inspection(out / "inspection.html", model_rows, comparison, baseline_rows)
    condition_metrics = {
        name: assembly.describe_metrics([item for item in model_rows if item["condition"] == name])
        for name in ("oracle_packet_9b", "dense_packet_9b")
    }
    comparison_counts = {
        "oracle_packet_9b": {key: sum(item["change"] == key for item in comparison if item["condition"] == "oracle_packet_9b") for key in ("improved", "declined", "unchanged")},
        "dense_packet_9b": {key: sum(item["change"] == key for item in comparison if item["condition"] == "dense_packet_9b") for key in ("improved", "declined", "unchanged")},
        "four_b_error_nine_b_correct": sum(item["four_b_error_nine_b_correct"] for item in comparison),
        "both_error": sum(item["both_error"] for item in comparison),
        "new_hallucination": sum(item["new_hallucination"] for item in comparison),
        "new_citation_error": sum(item["new_citation_error"] for item in comparison),
    }
    oracle = condition_metrics["oracle_packet_9b"]
    dense = condition_metrics["dense_packet_9b"]
    oracle_acceptance = {
        "answerable_correctness_ge_0_90": oracle["answerable_correctness"] >= 0.90,
        "required_fact_recall_ge_0_95": oracle["required_fact_recall"] >= 0.95,
        "citation_validity_eq_1": oracle["citation_validity_answered"] == 1.0,
        "citation_support_ge_0_95": oracle["citation_support_rate"] >= 0.95,
        "unsupported_claim_le_0_05": oracle["unsupported_claim_rate"] <= 0.05,
        "false_refusal_le_0_10": oracle["false_refusal_rate"] <= 0.10,
        "unanswerable_abstention_ge_0_90": oracle["unanswerable_abstention_rate"] >= 0.90,
    }
    dense_acceptance = {
        "answerable_correctness_ge_0_85": dense["answerable_correctness"] >= 0.85,
        "oracle_gap_le_0_10": oracle["answerable_correctness"] - dense["answerable_correctness"] <= 0.10,
        "citation_validity_eq_1": dense["citation_validity_answered"] == 1.0,
        "citation_support_ge_0_90": dense["citation_support_rate"] >= 0.90,
        "unanswerable_abstention_ge_0_90": dense["unanswerable_abstention_rate"] >= 0.90,
    }
    metrics = {
        "study": "007_stronger_generation_model",
        "dataset": {"version": "006-v2", "path": str(args.dataset_v2), "sha256": sha256(args.dataset_v2), "query_count": len(rows), "answerable": sum(r["question_type"] == "answerable" for r in rows), "unanswerable": sum(r["question_type"] == "unanswerable" for r in rows)},
        "fixed_variables": {"evidence_packet_schema": "evidence-packet-v0.1", "context_size": CONTEXT_SIZE, "max_tokens": MAX_TOKENS, "temperature": 0, "top_p": 1, "top_k": 1, "seed": SEED, "reasoning": "off", "dense_top_k": 5, "llama_cpp": LLAMA_RELEASE, "bge_results_source": "006 fixed Dense Top-5", "no_extract_then_answer": True},
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "license": MODEL_LICENSE, "gguf_repo": GGUF_REPO, "gguf_revision": GGUF_REVISION, "gguf_file": GGUF_FILE, "gguf_size_bytes": GGUF_SIZE, "gguf_sha256": GGUF_SHA256, "text_only": True, "mmproj_downloaded": False},
        "baseline_006": {"oracle_packet": json.loads((args.metrics_006).read_text(encoding="utf-8"))["conditions"]["oracle_packet"], "dense_packet": json.loads((args.metrics_006).read_text(encoding="utf-8"))["conditions"]["dense_packet"]},
        "conditions": condition_metrics,
        "comparison": comparison_counts,
        "acceptance": {"oracle_packet": oracle_acceptance, "dense_packet": dense_acceptance, "quality_pass": all(oracle_acceptance.values()) and all(dense_acceptance.values()), "stable_completed": True},
        "smoke": {key: value for key, value in smoke.items() if key != "results"},
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    pagefile_after = psutil.swap_memory().used
    resource_report = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "model": metrics["model"],
        "runtime": {"name": "llama.cpp", "release": LLAMA_RELEASE, "path": str(args.llama_server.parent), "server": server_meta, "offline": True, "mmproj": None},
        "resources": {"peak_evaluator_rss_bytes": sampler.peak_evaluator_rss if sampler else None, "peak_server_rss_bytes": sampler.peak_server_rss if sampler else None, "peak_total_rss_bytes": sampler.peak_total_rss if sampler else None, "peak_gpu_memory_mib": sampler.peak_gpu_mib if sampler else None, "pagefile_before_bytes": sampler.pagefile_before if sampler else None, "pagefile_peak_used_bytes": sampler.peak_pagefile_used if sampler else None, "pagefile_after_bytes": pagefile_after, "pagefile_delta_after_bytes": pagefile_after - (sampler.pagefile_before if sampler else pagefile_after), "gpu_backend_used": "CPU (-ngl 0)"},
        "disk": {"model_size_bytes": args.model_path.stat().st_size, "d_free_bytes_after": psutil.disk_usage("D:\\").free},
        "smoke_report_path": str(out / "smoke_report.json"),
        "offline_repeatable": True,
        "no_model_or_cache_committed": True,
    }
    (out / "resource_report.json").write_text(json.dumps(resource_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"conditions": condition_metrics, "comparison": comparison_counts, "acceptance": metrics["acceptance"], "resources": resource_report["resources"]}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "formal"), required=True)
    parser.add_argument("--iteration-dir", type=Path, default=PROJECT_ROOT / "iterations/007_stronger_generation_model")
    parser.add_argument("--dataset-v2", type=Path, default=PROJECT_ROOT / "iterations/006_context_and_evidence_assembly/evaluation_dataset_v2.jsonl")
    parser.add_argument("--generation-006", type=Path, default=PROJECT_ROOT / "iterations/006_context_and_evidence_assembly/generation_results.jsonl")
    parser.add_argument("--metrics-006", type=Path, default=PROJECT_ROOT / "iterations/006_context_and_evidence_assembly/metrics.json")
    parser.add_argument("--evidence-units", type=Path, default=PROJECT_ROOT / "iterations/006_context_and_evidence_assembly/evidence_units.jsonl")
    parser.add_argument("--llama-server", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, default=Path("D:/AI-Lab/envs/retrieval-adaptation-lab-llama-cpp-round7"))
    parser.add_argument("--port", type=int, default=18082)
    args = parser.parse_args()
    args.iteration_dir.mkdir(parents=True, exist_ok=True)
    if args.model_path.stat().st_size != GGUF_SIZE or sha256(args.model_path).lower() != GGUF_SHA256:
        raise ValueError("Qwen3.5-9B GGUF size or SHA-256 does not match the locked provenance")
    rows = load_jsonl(args.dataset_v2)
    units = load_jsonl(args.evidence_units)
    by_id = {unit["unit_id"]: unit for unit in units}
    if len(rows) != 30 or len(by_id) != 29:
        raise ValueError("007 requires the unchanged 30-row 006-v2 dataset and 29 KnowledgeUnits")
    os.environ["HF_HOME"] = "D:/AI-Lab/cache/huggingface"
    os.environ["HF_HUB_CACHE"] = "D:/AI-Lab/cache/huggingface/hub"
    os.environ["HF_DATASETS_CACHE"] = "D:/AI-Lab/cache/huggingface/datasets"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    if args.mode == "smoke":
        return run_smoke(args, rows, by_id)
    return run_formal(args, rows, by_id)


if __name__ == "__main__":
    raise SystemExit(main())
