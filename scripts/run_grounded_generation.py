"""Run the fixed Closed Book / Oracle Context / Dense RAG generation study.

The script deliberately keeps the generation runtime outside the project Python
environment.  It talks only to a local llama.cpp server and uses the existing
BGE-M3 environment for the fixed Dense Top-5 retrieval step.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import psutil
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.semantic import DenseRetriever
from src.retrieval.tfidf import Document, load_corpus

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"
MODEL_REVISION = "cdbee75f17c01a7cc42f958dc650907174af0554"
GGUF_REPO = "unsloth/Qwen3-4B-Instruct-2507-GGUF"
GGUF_REVISION = "a06e946bb6b655725eafa393f4a9745d460374c9"
GGUF_FILE = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
GGUF_SHA256 = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
LLAMA_CPP_RELEASE = "b9968"
DENSE_TOP_K = 5
SEED = 42
MAX_TOKENS = 256
CONTEXT_SIZE = 8192


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_fact(value: str) -> str:
    return (
        str(value)
        .casefold()
        .replace("摄氏度", "℃")
        .replace("°c", "℃")
        .replace("°c", "℃")
        .replace(" ", "")
        .replace("　", "")
        .replace("\n", "")
        .replace("\r", "")
    )


def fact_in_text(fact: str, text: str) -> bool:
    return normalize_fact(fact) in normalize_fact(text)


def forbidden_in_answer(fact: str, answer: str) -> bool:
    """Match a conflicting fact unless the occurrence is explicitly negated."""
    target = normalize_fact(fact)
    text = normalize_fact(answer)
    start = 0
    negations = ("不能", "不可", "无法", "不", "无需", "而非", "不是", "未")
    while True:
        index = text.find(target, start)
        if index < 0:
            return False
        prefix = text[max(0, index - 4) : index]
        if not any(prefix.endswith(negation) for negation in negations):
            return True
        start = index + max(1, len(target))


def claim_supported(claim: str, context: str, known_facts: list[str]) -> bool:
    """Conservative deterministic support check for model-produced fact strings."""
    if not context:
        return False
    if fact_in_text(claim, context):
        return True
    clauses = [
        normalize_fact(part)
        for part in re.split(r"[|,，:：;；。！？!?/]+|对应|现象为|处理方法是|处理措施是|表示|代表|是|为", claim)
        if normalize_fact(part)
    ]
    if not clauses:
        return False
    normalized_context = normalize_fact(context)
    for clause in clauses:
        if clause in normalized_context:
            continue
        if any(normalize_fact(fact) in clause and fact_in_text(fact, context) for fact in known_facts):
            continue
        return False
    return True


def extract_system_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "## System prompt"
    start = text.index("```text", text.index(marker)) + len("```text")
    end = text.index("```", start)
    return text[start:end].strip()


def make_user_prompt(query: str, context: str) -> str:
    return (
        "<context>\n"
        + (context if context else "（无资料）")
        + "\n</context>\n<question>\n"
        + query
        + "\n</question>\n请严格按上面的 JSON 规则回答。"
    )


def json_request(url: str, payload: dict[str, Any], timeout: float = 900.0) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class LocalLlamaServer:
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
            "-m",
            str(self.model),
            "-c",
            str(CONTEXT_SIZE),
            "-np",
            "1",
            "-ngl",
            "0",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--no-webui",
            "--offline",
            "--temp",
            "0",
            "--top-k",
            "1",
            "--seed",
            str(SEED),
            "-n",
            str(MAX_TOKENS),
            "--reasoning",
            "off",
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self.stdout_path.open("w", encoding="utf-8") as stdout, self.stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            self.process = subprocess.Popen(
                args,
                cwd=str(self.executable.parent),
                stdout=stdout,
                stderr=stderr,
                text=True,
                creationflags=creationflags,
            )
        health_url = self.url + "/health"
        for _ in range(180):
            if self.process.poll() is not None:
                error = self.stderr_path.read_text(encoding="utf-8", errors="replace")
                raise RuntimeError(f"llama-server exited with {self.process.returncode}: {error[-2000:]}")
            try:
                if get_json(health_url, timeout=2).get("status") in {"ok", "loading"}:
                    # /health returns 200 only after the model is ready in current builds.
                    if get_json(health_url, timeout=2).get("status") == "ok":
                        break
            except Exception:
                pass
            time.sleep(2)
        else:
            error = self.stderr_path.read_text(encoding="utf-8", errors="replace")
            raise TimeoutError(f"llama-server did not become healthy: {error[-2000:]}")
        return {"url": self.url, "pid": self.process.pid, "stderr": str(self.stderr_path)}

    def stop(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
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

    @staticmethod
    def gpu_memory_mib() -> int:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            values = [int(value.strip()) for value in result.stdout.splitlines() if value.strip().isdigit()]
            return max(values, default=0)
        except Exception:
            return 0

    def __enter__(self) -> "ResourceSampler":
        evaluator = psutil.Process()
        self.peak_evaluator_rss = evaluator.memory_info().rss
        self.peak_gpu_mib = self.gpu_memory_mib()

        def sample() -> None:
            while not self.stop_event.wait(0.05):
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
                    self.peak_gpu_mib = max(self.peak_gpu_mib, self.gpu_memory_mib())
                except (psutil.Error, OSError):
                    continue

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)


def parse_generation(response: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    choices = response.get("choices") or []
    content = ""
    if choices:
        content = str((choices[0].get("message") or {}).get("content") or "")
    parsed: dict[str, Any] = {}
    try:
        candidate = json.loads(content)
        if isinstance(candidate, dict):
            parsed = candidate
    except json.JSONDecodeError:
        parsed = {}
    return content, parsed, response.get("timings") or {}


def validate_response(parsed: dict[str, Any], content_ids: set[str]) -> dict[str, Any]:
    expected_keys = {"status", "answer", "citations", "used_facts"}
    schema_valid = (
        isinstance(parsed, dict)
        and set(parsed) == expected_keys
        and parsed.get("status") in {"answered", "insufficient_evidence"}
        and isinstance(parsed.get("answer"), str)
        and isinstance(parsed.get("citations"), list)
        and all(isinstance(item, str) for item in parsed.get("citations", []))
        and isinstance(parsed.get("used_facts"), list)
        and all(isinstance(item, str) for item in parsed.get("used_facts", []))
    )
    citations = parsed.get("citations", []) if isinstance(parsed, dict) else []
    citation_valid = schema_valid and all(item in content_ids for item in citations)
    return {
        "schema_valid": bool(schema_valid),
        "citation_valid": bool(citation_valid),
        "status": parsed.get("status") if isinstance(parsed, dict) else None,
        "answer": parsed.get("answer", "") if isinstance(parsed, dict) else "",
        "citations": citations if isinstance(citations, list) else [],
        "used_facts": parsed.get("used_facts", []) if isinstance(parsed, dict) else [],
    }


def evaluate_row(
    row: dict[str, Any],
    condition: str,
    context_ids: list[str],
    context_text: str,
    content: str,
    parsed: dict[str, Any],
    timings: dict[str, Any],
    total_ms: float,
    input_tokens: int | None,
    output_tokens: int | None,
    first_token_ms: float | None,
    retrieval_failure: bool,
) -> dict[str, Any]:
    checked = validate_response(parsed, set(context_ids))
    answerable = row["question_type"] == "answerable"
    status_correct = checked["status"] == ("answered" if answerable else "insufficient_evidence")
    answer_text = checked["answer"]
    combined_text = answer_text + " " + " ".join(checked["used_facts"])
    fact_hits = [fact_in_text(fact, combined_text) for fact in row["required_facts"]]
    forbidden_hits = [fact for fact in row["forbidden_or_conflicting_facts"] if forbidden_in_answer(fact, answer_text)]
    required_recall = sum(fact_hits) / len(fact_hits) if fact_hits else (1.0 if not answerable else 0.0)
    answer_correct = bool(status_correct and required_recall == 1.0 and not forbidden_hits)
    if not answerable:
        answer_correct = bool(status_correct)

    cited_text = "\n".join(
        f"[{unit_id}] {context_text.split(f'[{unit_id}] ', 1)[1].splitlines()[0]}"
        for unit_id in checked["citations"]
        if f"[{unit_id}] " in context_text
    )
    citation_supported_facts = [
        any(fact_in_text(fact, cited_text) for _ in [0]) for fact in row["required_facts"]
    ]
    citation_support_rate = (
        sum(citation_supported_facts) / len(citation_supported_facts)
        if citation_supported_facts
        else (1.0 if not answerable else 0.0)
    )
    unsupported_used_facts = [
        fact for fact in checked["used_facts"]
        if not claim_supported(fact, context_text, row["required_facts"])
    ]
    unsupported_answer_facts = [
        fact for fact in row["required_facts"]
        if fact_in_text(fact, answer_text) and not fact_in_text(fact, context_text)
    ]
    unsupported_claim = bool(unsupported_used_facts or unsupported_answer_facts or forbidden_hits)
    citation_failure = bool(not checked["citation_valid"] or (answerable and citation_support_rate < 1.0))
    if retrieval_failure:
        failure_source = "retrieval_failure"
    elif not answer_correct:
        failure_source = "generation_failure"
    elif citation_failure:
        failure_source = "citation_failure"
    else:
        failure_source = "none"
    return {
        "query_id": row["query_id"],
        "condition": condition,
        "question_type": row["question_type"],
        "query": row["query"],
        "reference_answer": row.get("reference_answer"),
        "required_facts": row["required_facts"],
        "forbidden_or_conflicting_facts": row["forbidden_or_conflicting_facts"],
        "context_unit_ids": context_ids,
        "context_text": context_text,
        "retrieval_failure": bool(retrieval_failure),
        "raw_model_output": content,
        "parsed_output": parsed,
        "status": checked["status"],
        "answer": answer_text,
        "citations": checked["citations"],
        "used_facts": checked["used_facts"],
        "schema_valid": checked["schema_valid"],
        "citation_valid": checked["citation_valid"],
        "citation_support_rate": citation_support_rate,
        "required_fact_recall": required_recall,
        "unsupported_claim": unsupported_claim,
        "unsupported_used_facts": unsupported_used_facts,
        "unsupported_answer_facts": unsupported_answer_facts,
        "forbidden_hits": forbidden_hits,
        "answer_correct": answer_correct,
        "status_correct": status_correct,
        "failure_source": failure_source,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_generation_ms": total_ms,
        "first_token_latency_ms": first_token_ms,
        "prompt_eval_ms": timings.get("prompt_ms"),
        "generation_eval_ms": timings.get("predicted_ms"),
        "generation_tokens_per_second": (
            float(timings.get("predicted_per_second")) if timings.get("predicted_per_second") is not None else None
        ),
    }


def stats(values: list[float | int | None]) -> dict[str, float | None]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return {"average": None, "p50": None, "p95": None}
    return {
        "average": statistics.fmean(clean),
        "p50": float(np.percentile(clean, 50)),
        "p95": float(np.percentile(clean, 95)),
    }


def condition_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [row for row in rows if row["question_type"] == "answerable"]
    unanswerable = [row for row in rows if row["question_type"] == "unanswerable"]
    fact_total = sum(len(row["required_facts"]) for row in answerable)
    fact_recalled = sum(round(row["required_fact_recall"] * len(row["required_facts"])) for row in answerable)
    return {
        "query_count": len(rows),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "answer_correctness": sum(row["answer_correct"] for row in rows) / len(rows),
        "answerable_correctness": sum(row["answer_correct"] for row in answerable) / len(answerable),
        "required_fact_recall": fact_recalled / fact_total if fact_total else 0.0,
        "unsupported_claim_rate": sum(row["unsupported_claim"] for row in rows) / len(rows),
        "citation_validity": sum(row["citation_valid"] for row in rows) / len(rows),
        "citation_support_rate": sum(row["citation_support_rate"] for row in answerable) / len(answerable),
        "unanswerable_abstention_rate": sum(row["status"] == "insufficient_evidence" for row in unanswerable) / len(unanswerable),
        "false_refusal_rate": sum(row["status"] == "insufficient_evidence" for row in answerable) / len(answerable),
        "json_schema_pass_rate": sum(row["schema_valid"] for row in rows) / len(rows),
        "latency_ms": {
            "total_generation": stats([row["total_generation_ms"] for row in rows]),
            "first_token": stats([row["first_token_latency_ms"] for row in rows]),
        },
        "input_tokens": stats([row["input_tokens"] for row in rows]),
        "output_tokens": stats([row["output_tokens"] for row in rows]),
        "tokens_per_second": stats([row["generation_tokens_per_second"] for row in rows]),
        "failure_counts": {
            "retrieval_failure": sum(row["failure_source"] == "retrieval_failure" for row in rows),
            "generation_failure": sum(row["failure_source"] == "generation_failure" for row in rows),
            "citation_failure": sum(row["failure_source"] == "citation_failure" for row in rows),
            "any_failure": sum(row["failure_source"] != "none" for row in rows),
        },
    }


def write_failures(path: Path, rows: list[dict[str, Any]]) -> None:
    failures = [row for row in rows if row["failure_source"] != "none"]
    fields = [
        "query_id",
        "condition",
        "question_type",
        "query",
        "failure_source",
        "retrieval_failure",
        "schema_valid",
        "citation_valid",
        "citation_support_rate",
        "required_fact_recall",
        "answer",
        "citations",
        "context_unit_ids",
        "observation",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in failures:
            observations: list[str] = []
            if row["retrieval_failure"]:
                observations.append("Dense Top-5 未包含人工标注的相关 KnowledgeUnit。")
            if not row["schema_valid"]:
                observations.append("模型输出无法通过固定 JSON Schema。")
            if not row["citation_valid"]:
                observations.append("引用 ID 不在当前 Context 中。")
            if row["citation_support_rate"] < 1.0 and row["question_type"] == "answerable":
                observations.append("引用未覆盖全部人工要求事实。")
            if row["required_fact_recall"] < 1.0 and row["question_type"] == "answerable":
                observations.append("回答未包含全部要求事实。")
            if row["question_type"] == "unanswerable" and row["status"] == "answered":
                observations.append("资料不足题返回 answered，属于拒答失败。")
            writer.writerow(
                {
                    **{field: row.get(field) for field in fields if field not in {"citations", "context_unit_ids", "observation"}},
                    "citations": "|".join(row["citations"]),
                    "context_unit_ids": "|".join(row["context_unit_ids"]),
                    "observation": " ".join(observations),
                }
            )


def write_inspection(path: Path, rows: list[dict[str, Any]]) -> None:
    tr: list[str] = []
    for row in rows:
        tr.append(
            "<tr data-condition='{condition}' data-type='{qtype}' data-correct='{correct}' data-source='{source}'>"
            "<td>{condition}</td><td>{qtype}</td><td>{correct}</td><td>{source}</td>"
            "<td>{query}</td><td><details><summary>Context ({count})</summary><pre>{context}</pre></details></td>"
            "<td>{reference}</td><td>{answer}</td><td>{citations}</td></tr>".format(
                condition=html.escape(row["condition"]),
                qtype=html.escape(row["question_type"]),
                correct=str(row["answer_correct"]).lower(),
                source=html.escape(row["failure_source"]),
                query=html.escape(row["query"]),
                count=len(row["context_unit_ids"]),
                context=html.escape(row["context_text"]),
                reference=html.escape(str(row["reference_answer"] or row.get("required_facts") or "资料不足")),
                answer=html.escape(row["answer"]),
                citations=html.escape("|".join(row["citations"])),
            )
        )
    page = """<!doctype html><meta charset=utf-8><title>005 grounded generation inspection</title>
<style>body{font:14px system-ui;margin:24px}select{margin:4px;padding:5px}table{border-collapse:collapse;width:100%}th,td{padding:7px;border-bottom:1px solid #ddd;vertical-align:top}th{position:sticky;top:0;background:#17324d;color:white}pre{white-space:pre-wrap;max-width:560px}details{max-width:600px}</style>
<h1>005 Grounded Generation 检查</h1>
<p>固定三条件：Closed Book / Oracle Context / Dense RAG；Dense Top-5；模型输出和人工规则并列展示。</p>
<div><select data-k=condition><option value=''>全部条件</option><option>closed_book</option><option>oracle_context</option><option>dense_rag</option></select>
<select data-k=type><option value=''>全部问题</option><option>answerable</option><option>unanswerable</option></select>
<select data-k=correct><option value=''>全部正确性</option><option value='true'>正确</option><option value='false'>错误</option></select>
<select data-k=source><option value=''>全部错误来源</option><option>none</option><option>retrieval_failure</option><option>generation_failure</option><option>citation_failure</option></select></div>
<table><thead><tr><th>条件</th><th>问题类型</th><th>正确</th><th>错误来源</th><th>Query</th><th>Context</th><th>Reference / Facts</th><th>实际回答</th><th>Citations</th></tr></thead><tbody>""" + "".join(tr) + """</tbody></table>
<script>const ss=[...document.querySelectorAll('select')],rs=[...document.querySelectorAll('tbody tr')];function f(){rs.forEach(r=>r.hidden=ss.some(s=>s.value&&r.dataset[s.dataset.k]!==s.value))}ss.forEach(s=>s.onchange=f)</script>"""
    path.write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration-dir", type=Path, default=PROJECT_ROOT / "iterations/005_grounded_generation")
    parser.add_argument("--dataset", type=Path, default=PROJECT_ROOT / "iterations/005_grounded_generation/evaluation_dataset.jsonl")
    parser.add_argument("--prompt", type=Path, default=PROJECT_ROOT / "iterations/005_grounded_generation/PROMPT.md")
    parser.add_argument("--mx100-corpus", type=Path, required=True)
    parser.add_argument("--bge-model-path", type=Path, required=True)
    parser.add_argument("--llama-server", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, default=Path("D:/AI-Lab/envs/retrieval-adaptation-lab-llama-cpp"))
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()

    out = args.iteration_dir
    out.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(args.dataset)
    if len(rows) < 30 or sum(row["question_type"] == "answerable" for row in rows) < 20 or sum(row["question_type"] == "unanswerable" for row in rows) < 10:
        raise ValueError("Evaluation dataset must contain at least 20 answerable and 10 unanswerable questions")
    if sha256(args.model_path).lower() != GGUF_SHA256:
        raise ValueError("GGUF SHA-256 does not match the preflight lock")
    system_prompt = extract_system_prompt(args.prompt)

    # Keep all Hugging Face/cache variables process-local and on D:.
    os.environ.setdefault("HF_HOME", "D:/AI-Lab/cache/huggingface")
    os.environ.setdefault("HF_HUB_CACHE", "D:/AI-Lab/cache/huggingface/hub")
    os.environ.setdefault("HF_DATASETS_CACHE", "D:/AI-Lab/cache/huggingface/datasets")
    os.environ.setdefault("TRANSFORMERS_CACHE", "D:/AI-Lab/cache/huggingface/transformers")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    docs = load_corpus(args.mx100_corpus)
    document_map = {doc.document_id: doc.text for doc in docs}
    model_load_started = time.perf_counter()
    dense_encoder = SentenceTransformer(str(args.bge_model_path), device="cpu", local_files_only=True)
    dense_encoder.max_seq_length = 8192
    model_load_seconds = time.perf_counter() - model_load_started
    dense = DenseRetriever(dense_encoder, batch_size=4)
    dense_build = dense.fit(docs)

    server = LocalLlamaServer(args.llama_server, args.model_path, args.runtime_dir, args.port)
    server_meta = server.start()
    generation_rows: list[dict[str, Any]] = []
    process_sampler = ResourceSampler(server.process.pid if server.process else None)
    process_sampler.__enter__()
    try:
        for row in rows:
            contexts: list[tuple[str, list[str], str, bool]] = []
            oracle_ids = [unit_id for unit_id in row["relevant_unit_ids"] if unit_id in document_map]
            oracle_context = "\n".join(f"[{unit_id}] {document_map[unit_id]}" for unit_id in oracle_ids)
            contexts.append(("closed_book", [], "", False))
            contexts.append(("oracle_context", oracle_ids, oracle_context, False))
            dense_results = dense.search(row["query"], top_k=DENSE_TOP_K)
            dense_ids = [result.document_id for result in dense_results]
            dense_context = "\n".join(f"[{unit_id}] {document_map[unit_id]}" for unit_id in dense_ids)
            dense_miss = (
                row["question_type"] == "answerable"
                and not set(dense_ids).intersection(row["relevant_unit_ids"])
                and not any(fact_in_text(fact, dense_context) for fact in row["required_facts"])
            )
            contexts.append(("dense_rag", dense_ids, dense_context, dense_miss))
            for condition, context_ids, context_text, retrieval_failure in contexts:
                user_prompt = make_user_prompt(row["query"], context_text)
                payload = {
                    "model": str(args.model_path),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "top_p": 1,
                    "top_k": 1,
                    "seed": SEED,
                    "max_tokens": MAX_TOKENS,
                    "stream": False,
                }
                started = time.perf_counter()
                response = json_request(server.url + "/v1/chat/completions", payload)
                total_ms = (time.perf_counter() - started) * 1000
                content, parsed, timings = parse_generation(response)
                usage = response.get("usage") or {}
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")
                predicted_ms = timings.get("predicted_ms")
                predicted_per_token_ms = timings.get("predicted_per_token_ms")
                first_token_ms = None
                if predicted_ms is not None and predicted_per_token_ms is not None:
                    first_token_ms = float(timings.get("prompt_ms", 0)) + float(predicted_per_token_ms)
                evaluated = evaluate_row(
                    row,
                    condition,
                    context_ids,
                    context_text,
                    content,
                    parsed,
                    timings,
                    total_ms,
                    input_tokens,
                    output_tokens,
                    first_token_ms,
                    retrieval_failure,
                )
                evaluated["server_timings"] = timings
                evaluated["server_id"] = response.get("id")
                evaluated["model_fingerprint"] = response.get("system_fingerprint")
                generation_rows.append(evaluated)
    finally:
        process_sampler.__exit__(None, None, None)
        server.stop()

    (out / "generation_results.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in generation_rows) + "\n", encoding="utf-8"
    )
    metrics = {
        "study": "005_grounded_generation",
        "dataset": {"path": str(args.dataset), "query_count": len(rows), "answerable": sum(row["question_type"] == "answerable" for row in rows), "unanswerable": sum(row["question_type"] == "unanswerable" for row in rows), "source": "002/003 fictitious MX-100 KnowledgeUnits and 004 Chinese evaluation basis"},
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "gguf_repo": GGUF_REPO, "gguf_revision": GGUF_REVISION, "gguf_file": GGUF_FILE, "gguf_sha256": GGUF_SHA256, "runtime": f"llama.cpp {LLAMA_CPP_RELEASE}"},
        "fixed_generation": {"temperature": 0, "top_p": 1, "top_k": 1, "seed": SEED, "max_tokens": MAX_TOKENS, "context_size": CONTEXT_SIZE, "reasoning": "off", "prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()},
        "retrieval": {"method": "BAAI/bge-m3 Dense", "top_k": DENSE_TOP_K, "model_path": str(args.bge_model_path), "build_seconds": dense_build.seconds, "document_count": len(dense.documents)},
        "conditions": {condition: condition_metrics([row for row in generation_rows if row["condition"] == condition]) for condition in ("closed_book", "oracle_context", "dense_rag")},
        "resource_observation": {"model_load_seconds": model_load_seconds, "peak_evaluator_rss_bytes": process_sampler.peak_evaluator_rss, "peak_server_rss_bytes": process_sampler.peak_server_rss, "peak_total_rss_bytes": process_sampler.peak_total_rss, "peak_gpu_memory_mib_observed": process_sampler.peak_gpu_mib, "gpu_backend_used": "cpu"},
    }
    oracle = metrics["conditions"]["oracle_context"]
    metrics["acceptance"] = {
        "oracle_answerable_correctness_ge_0_90": oracle["answerable_correctness"] >= 0.90,
        "oracle_citation_validity_eq_1": oracle["citation_validity"] == 1.0,
        "oracle_citation_support_ge_0_95": oracle["citation_support_rate"] >= 0.95,
        "oracle_unsupported_claim_rate_le_0_05": oracle["unsupported_claim_rate"] <= 0.05,
        "oracle_unanswerable_abstention_ge_0_90": oracle["unanswerable_abstention_rate"] >= 0.90,
        "dense_close_to_oracle": metrics["conditions"]["dense_rag"]["answerable_correctness"] >= oracle["answerable_correctness"] - 0.10,
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    write_failures(out / "failures.csv", generation_rows)
    write_inspection(out / "inspection.html", generation_rows)

    try:
        gpu_info = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=20, check=False).stdout.strip()
    except Exception as error:
        gpu_info = f"unavailable:{error}"
    runtime_bytes = sum(item.stat().st_size for item in args.llama_server.parent.rglob("*") if item.is_file())
    d_free = None
    try:
        d_free = next(item for item in psutil.disk_partitions() if item.mountpoint.upper().startswith("D:"))
        d_free_bytes = psutil.disk_usage(d_free.mountpoint).free
    except Exception:
        d_free_bytes = None
    resource_report = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "project_root": str(PROJECT_ROOT),
        "runtime": {"name": "llama.cpp", "release": LLAMA_CPP_RELEASE, "path": str(args.llama_server.parent), "bytes": runtime_bytes, "backend": "CPU", "server": server_meta, "offline_flag": True},
        "model": {"path": str(args.model_path), "bytes": args.model_path.stat().st_size, "sha256": sha256(args.model_path), "base_revision": MODEL_REVISION},
        "bge_model_path": str(args.bge_model_path),
        "peak_evaluator_rss_bytes": process_sampler.peak_evaluator_rss,
        "peak_server_rss_bytes": process_sampler.peak_server_rss,
        "peak_total_rss_bytes": process_sampler.peak_total_rss,
        "peak_gpu_memory_mib_observed": process_sampler.peak_gpu_mib,
        "gpu_backend_used": "cpu",
        "gpu_device": gpu_info,
        "d_drive_free_bytes_after": d_free_bytes,
        "pip_check": subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True, check=False).stdout.strip(),
        "offline_repeatable": True,
        "no_model_or_cache_committed": True,
    }
    (out / "resource_report.json").write_text(json.dumps(resource_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": metrics["conditions"], "acceptance": metrics["acceptance"], "failures": sum(row["failure_source"] != "none" for row in generation_rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
