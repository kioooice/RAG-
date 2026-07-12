"""Round 8 MiMo cloud-generation runner.

The runner is intentionally standard-library-only.  It reads credentials from
the current process first and then from the external INI file.  It never writes
the key to a request body, log, manifest, report, or repository file.

``--preflight`` is offline. ``--smoke`` performs exactly the six approved
smoke requests when preflight succeeds. ``--full`` requires a passing smoke
run (or performs it once) before the 60 formal Oracle/Dense requests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.generation.credentials import CredentialConfig, load_credentials


ROUND_DIR = PROJECT_ROOT / "iterations/008_cloud_generation_upper_bound"
DATASET_PATH = PROJECT_ROOT / "iterations/006_context_and_evidence_assembly/evaluation_dataset_v2.jsonl"
CONTEXT_RESULTS_PATH = PROJECT_ROOT / "iterations/006_context_and_evidence_assembly/generation_results.jsonl"
LOCAL_9B_RESULTS_PATH = PROJECT_ROOT / "iterations/007_stronger_generation_model/generation_results.jsonl"
PROMPT_PATH = PROJECT_ROOT / "iterations/005_grounded_generation/PROMPT.md"
MODEL = "mimo-v2.5-pro"
SMOKE_QUERY_IDS = ("mxq-001", "mxq-002", "mxq-022")
FORMAL_CONDITIONS = (("oracle_packet", "oracle"), ("dense_packet", "dense"))
MAX_COMPLETION_TOKENS = 256
TEMPERATURE = 0.0
TOP_P = 1.0
RETRY_LIMIT = 2
REQUEST_TIMEOUT_SECONDS = 90

# Official MiMo pay-as-you-go rates shown on the public English pricing page.
# Token Plan requests are not assigned a per-token USD price here.
PAYG_INPUT_MISS_USD_PER_MTOK = 0.435
PAYG_INPUT_CACHE_HIT_USD_PER_MTOK = 0.0036
PAYG_OUTPUT_USD_PER_MTOK = 0.87

FORBIDDEN_PAYLOAD_PATTERNS = (
    re.compile(r"(?i)(?:[a-z]:\\|[a-z]:/|\\\\)"),
    re.compile(r"(?i)\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)0\d{2,3}[- ]?\d{7,8}(?!\d)"),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    re.compile(r"(?i)\b(?:MIMO_API_KEY|AUTHORIZATION|BEARER)\b"),
    re.compile(r"公司|部门|邮箱|电话|身份证|Notebook|Git"),
)

FORBIDDEN_MESSAGE_PATTERNS = (
    re.compile(r"(?i)\b(?:xiaomi|mimo|qwen|openai|codex|ragbench|administrator)\b"),
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def safe_payload_check(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in FORBIDDEN_PAYLOAD_PATTERNS:
        if pattern.search(serialized):
            raise ValueError("payload_boundary_violation")
    messages_serialized = json.dumps(payload.get("messages", []), ensure_ascii=False, sort_keys=True)
    for pattern in FORBIDDEN_MESSAGE_PATTERNS:
        if pattern.search(messages_serialized):
            raise ValueError("payload_boundary_violation")
    if "response_format" not in payload or payload["response_format"] != {"type": "json_object"}:
        raise ValueError("structured_output_not_enabled")
    if payload.get("stream") is not False:
        raise ValueError("stream_must_be_false")
    if payload.get("thinking") != {"type": "disabled"}:
        raise ValueError("thinking_must_be_disabled")
    if payload.get("tools") or payload.get("tool_choice"):
        raise ValueError("tools_must_be_disabled")


def extract_system_prompt() -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    match = re.search(r"## System prompt\s+```text\n(.*?)\n```", text, flags=re.S)
    if not match:
        raise RuntimeError("fixed_system_prompt_not_found")
    return match.group(1).strip()


def packet_user(query: str, packet_text: str) -> str:
    return (
        "<context>\n"
        + (packet_text if packet_text else "（无资料）")
        + "\n</context>\n<question>\n"
        + query
        + "\n</question>\n"
        "只允许引用 context 中明确列出的 knowledge_unit_id；请严格按 JSON 规则回答。"
    )


def load_fixed_inputs() -> tuple[list[dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    if not DATASET_PATH.exists() or not CONTEXT_RESULTS_PATH.exists() or not PROMPT_PATH.exists():
        raise FileNotFoundError("fixed_round_6_inputs_missing")
    dataset = load_jsonl(DATASET_PATH)
    context_rows = load_jsonl(CONTEXT_RESULTS_PATH)
    by_id = {row["query_id"]: row for row in dataset}
    if len(dataset) != 30 or set(by_id) != {row["query_id"] for row in dataset}:
        raise RuntimeError("evaluation_dataset_v2_must_contain_30_unique_queries")
    packets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in context_rows:
        condition = row.get("condition")
        if condition in {"oracle_packet", "dense_packet"}:
            packets[(row["query_id"], condition)] = row
    for query_id in by_id:
        for condition, _ in FORMAL_CONDITIONS:
            if (query_id, condition) not in packets:
                raise RuntimeError("fixed_evidence_packet_missing")
    return dataset, packets


def make_payload(system_prompt: str, query: str, packet_row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": packet_user(query, str(packet_row.get("packet_text") or ""))},
        ],
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "stream": False,
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
    }
    safe_payload_check(payload)
    return payload


def normalize_fact(value: Any) -> str:
    return (
        str(value or "")
        .casefold()
        .replace("摄氏度", "℃")
        .replace("°c", "℃")
        .replace(" ", "")
        .replace("　", "")
        .replace("\n", "")
        .replace("\r", "")
    )


def fact_in_text(fact: str, text: str) -> bool:
    return normalize_fact(fact) in normalize_fact(text)


def forbidden_in_answer(fact: str, answer: str) -> bool:
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


def parse_content(response: dict[str, Any]) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    choices = response.get("choices") or []
    message = choices[0].get("message") if choices else {}
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return "", None, message if isinstance(message, dict) else {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content, None, message if isinstance(message, dict) else {}
    return content, parsed if isinstance(parsed, dict) else None, message if isinstance(message, dict) else {}


def validate_output(parsed: dict[str, Any] | None, allowed_ids: set[str]) -> dict[str, Any]:
    schema = (
        isinstance(parsed, dict)
        and set(parsed) == {"status", "answer", "citations", "used_facts"}
        and parsed.get("status") in {"answered", "insufficient_evidence"}
        and isinstance(parsed.get("answer"), str)
        and isinstance(parsed.get("citations"), list)
        and all(isinstance(value, str) for value in parsed.get("citations", []))
        and isinstance(parsed.get("used_facts"), list)
        and all(isinstance(value, str) for value in parsed.get("used_facts", []))
    )
    citations = parsed.get("citations", []) if isinstance(parsed, dict) else []
    citation_valid = bool(schema and all(value in allowed_ids for value in citations))
    return {
        "schema_valid": bool(schema),
        "citation_valid": citation_valid,
        "status": parsed.get("status") if isinstance(parsed, dict) else None,
        "answer": parsed.get("answer", "") if isinstance(parsed, dict) else "",
        "citations": citations if isinstance(citations, list) else [],
        "used_facts": parsed.get("used_facts", []) if isinstance(parsed, dict) else [],
    }


def evaluate_result(query_row: dict[str, Any], packet_row: dict[str, Any], parsed: dict[str, Any] | None, response_model: str | None, usage: dict[str, Any], latency_ms: float, error: str | None = None) -> dict[str, Any]:
    packet_ids = list(packet_row.get("packet_allowed_ids") or [])
    checked = validate_output(parsed, set(packet_ids))
    answer = checked["answer"]
    used_facts = checked["used_facts"]
    answerable = query_row.get("question_type") == "answerable"
    fact_hits = [fact_in_text(fact, answer + " " + " ".join(used_facts)) for fact in query_row.get("required_facts", [])]
    required_recall = sum(fact_hits) / len(fact_hits) if fact_hits else (1.0 if not answerable else 0.0)
    status_correct = checked["status"] == ("answered" if answerable else "insufficient_evidence")
    forbidden_hits = [
        fact for fact in query_row.get("forbidden_or_conflicting_facts", [])
        if checked["status"] == "answered" and forbidden_in_answer(fact, answer)
    ]
    answer_correct = bool(status_correct and (not answerable or required_recall == 1.0) and not forbidden_hits)
    citation_text = "\n".join(
        unit.get("content", unit.get("text", ""))
        for unit in packet_row.get("packet_units", [])
        if unit.get("knowledge_unit_id") in checked["citations"]
    )
    citation_hits = [fact_in_text(fact, citation_text) for fact in query_row.get("required_facts", [])]
    citation_coverage = sum(citation_hits) / len(citation_hits) if citation_hits else (1.0 if not answerable else 0.0)
    unsupported_used = [
        fact for fact in used_facts
        if fact and not fact_in_text(fact, str(packet_row.get("packet_text") or ""))
    ]
    unsupported_claim = bool(forbidden_hits or unsupported_used)
    failures: list[str] = []
    if error:
        failures.append(error)
    if not checked["schema_valid"]:
        failures.append("schema_error")
    if not checked["citation_valid"]:
        failures.append("citation_error")
    if answerable and checked["status"] == "insufficient_evidence":
        failures.append("false_refusal")
    if not answerable and checked["status"] == "answered":
        failures.append("missed_abstention")
    if answerable and required_recall < 1.0:
        failures.append("required_fact_miss")
    if forbidden_hits:
        failures.append("conflict_fact")
    return {
        "query_id": query_row["query_id"],
        "query": query_row["query"],
        "question_type": query_row.get("question_type"),
        "condition": packet_row.get("condition"),
        "context_unit_ids": packet_ids,
        "packet_text": packet_row.get("packet_text", ""),
        "packet_units": packet_row.get("packet_units", []),
        "reference_answer": query_row.get("reference_answer"),
        "required_facts": query_row.get("required_facts", []),
        "relevant_unit_ids": query_row.get("relevant_unit_ids", []),
        "parsed_output": parsed if isinstance(parsed, dict) else {},
        "status": checked["status"],
        "answer": answer,
        "citations": checked["citations"],
        "schema_valid": checked["schema_valid"],
        "citation_valid": checked["citation_valid"],
        "citation_coverage": citation_coverage,
        "citation_support": citation_coverage,
        "required_fact_recall": required_recall,
        "answer_correct": answer_correct,
        "status_correct": status_correct,
        "unsupported_claim": unsupported_claim,
        "unsupported_used_facts": unsupported_used,
        "forbidden_hits": forbidden_hits,
        "failure_types": list(dict.fromkeys(failures)),
        "response_model": response_model,
        "usage": usage,
        "latency_ms": latency_ms,
    }


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def estimate_cost(dataset: list[dict[str, Any]], packets: dict[tuple[str, str], dict[str, Any]], system_prompt: str, requests: int) -> dict[str, Any]:
    prompt_tokens = 0
    for row in dataset:
        for condition, _ in FORMAL_CONDITIONS:
            packet = packets[(row["query_id"], condition)]
            prompt_tokens += estimate_tokens(system_prompt + packet_user(row["query"], packet.get("packet_text", "")))
    average_prompt = prompt_tokens / max(1, len(dataset) * len(FORMAL_CONDITIONS))
    estimated_input = average_prompt * requests
    estimated_output = MAX_COMPLETION_TOKENS * requests
    estimated_usd = (estimated_input * PAYG_INPUT_MISS_USD_PER_MTOK + estimated_output * PAYG_OUTPUT_USD_PER_MTOK) / 1_000_000
    return {
        "requests": requests,
        "average_prompt_tokens_estimate": round(average_prompt, 2),
        "max_output_tokens_per_request": MAX_COMPLETION_TOKENS,
        "payg_worst_case_usd_estimate": round(estimated_usd, 8),
        "payg_rates_source": "mimo.mi.com/docs/welcome",
    }


def manifest_path() -> Path:
    return ROUND_DIR / "request_manifest.jsonl"


def existing_attempts() -> int:
    path = manifest_path()
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def write_manifest(record: dict[str, Any]) -> None:
    ROUND_DIR.mkdir(parents=True, exist_ok=True)
    safe = {key: value for key, value in record.items() if key not in {"payload", "headers", "api_key", "authorization"}}
    with manifest_path().open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")


def extract_usage(response: dict[str, Any]) -> dict[str, Any]:
    usage = response.get("usage") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "input_tokens": usage.get("prompt_tokens"),
        "cached_tokens": prompt_details.get("cached_tokens"),
        "reasoning_tokens": completion_details.get("reasoning_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def request_cost(usage: dict[str, Any], config: CredentialConfig) -> float | None:
    # A Token Plan has no per-request USD price in the official documentation.
    if config.base_url.startswith("https://token-plan-"):
        return None
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    cached = usage.get("cached_tokens") or 0
    if not isinstance(cached, int):
        cached = 0
    uncached = max(0, input_tokens - cached)
    return (
        uncached * PAYG_INPUT_MISS_USD_PER_MTOK / 1_000_000
        + cached * PAYG_INPUT_CACHE_HIT_USD_PER_MTOK / 1_000_000
        + output_tokens * PAYG_OUTPUT_USD_PER_MTOK / 1_000_000
    )


def http_request(config: CredentialConfig, payload: dict[str, Any], phase: str, query_id: str, condition: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not config.has_key:
        raise RuntimeError("missing_credentials")
    if config.status != "ready":
        raise RuntimeError("credential_preflight_failed")
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    attempt = 0
    while True:
        if existing_attempts() >= config.max_requests:
            raise RuntimeError("request_limit_reached")
        attempt += 1
        started = time.perf_counter()
        request = urllib.request.Request(
            config.endpoint,
            data=body,
            headers={"api-key": config.api_key or "", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read()
            parsed = json.loads(raw.decode("utf-8"))
            latency_ms = (time.perf_counter() - started) * 1000
            usage = extract_usage(parsed if isinstance(parsed, dict) else {})
            cost = request_cost(usage, config)
            write_manifest({
                "phase": phase, "query_id": query_id, "condition": condition,
                "attempt": attempt, "status": "success", "http_status": 200,
                "model": MODEL, "response_model": parsed.get("model") if isinstance(parsed, dict) else None,
                "latency_ms": round(latency_ms, 3), "usage": usage, "cost_usd": cost,
            })
            return parsed if isinstance(parsed, dict) else None, {"latency_ms": latency_ms, "usage": usage, "cost_usd": cost, "retries": attempt - 1}
        except urllib.error.HTTPError as exc:
            category = "http_429" if exc.code == 429 else ("http_5xx" if exc.code >= 500 else "http_error")
            write_manifest({"phase": phase, "query_id": query_id, "condition": condition, "attempt": attempt, "status": "error", "http_status": exc.code, "error_category": category, "model": MODEL})
            if category in {"http_429", "http_5xx"} and attempt <= RETRY_LIMIT:
                time.sleep(2 ** (attempt - 1))
                continue
            return None, {"latency_ms": (time.perf_counter() - started) * 1000, "usage": {}, "cost_usd": None, "retries": attempt - 1, "error": category}
        except (TimeoutError, urllib.error.URLError):
            write_manifest({"phase": phase, "query_id": query_id, "condition": condition, "attempt": attempt, "status": "error", "error_category": "timeout_or_network", "model": MODEL})
            if attempt <= RETRY_LIMIT:
                time.sleep(2 ** (attempt - 1))
                continue
            return None, {"latency_ms": (time.perf_counter() - started) * 1000, "usage": {}, "cost_usd": None, "retries": attempt - 1, "error": "timeout_or_network"}
        except (json.JSONDecodeError, OSError):
            write_manifest({"phase": phase, "query_id": query_id, "condition": condition, "attempt": attempt, "status": "error", "error_category": "invalid_response", "model": MODEL})
            return None, {"latency_ms": (time.perf_counter() - started) * 1000, "usage": {}, "cost_usd": None, "retries": attempt - 1, "error": "invalid_response"}


def smoke_report_path() -> Path:
    return ROUND_DIR / "smoke_report.json"


def run_smoke(config: CredentialConfig, dataset: list[dict[str, Any]], packets: dict[tuple[str, str], dict[str, Any]], system_prompt: str) -> bool:
    needed = len(SMOKE_QUERY_IDS) * len(FORMAL_CONDITIONS)
    if existing_attempts() + needed > config.max_requests:
        print(json.dumps({"status": "blocked", "reason": "request_budget_exhausted"}, ensure_ascii=False))
        return False
    rows: list[dict[str, Any]] = []
    safe_checks: list[bool] = []
    for query_id in SMOKE_QUERY_IDS:
        query_row = next(row for row in dataset if row["query_id"] == query_id)
        for condition, _ in FORMAL_CONDITIONS:
            packet = packets[(query_id, condition)]
            payload = make_payload(system_prompt, query_row["query"], packet)
            safe_checks.append(True)
            response, info = http_request(config, payload, "smoke", query_id, condition)
            content, parsed, message = parse_content(response or {})
            response_model = (response or {}).get("model") if response else None
            usage = info.get("usage", {})
            output = evaluate_result(query_row, packet, parsed, response_model, usage, info.get("latency_ms", 0), info.get("error"))
            output["phase"] = "smoke"
            output["structured_output"] = bool(output["schema_valid"])
            output["response_model_correct"] = response_model == MODEL
            output["thinking_disabled_observed"] = not bool(message.get("reasoning_content"))
            output["tools_absent"] = not bool(message.get("tool_calls")) and not bool((response or {}).get("usage", {}).get("web_search_usage"))
            output["content_received"] = bool(content)
            output["retry_count"] = info.get("retries", 0)
            rows.append(output)
    passed = bool(rows) and all(
        row["structured_output"] and row["response_model_correct"] and row["thinking_disabled_observed"] and row["tools_absent"] and not row["failure_types"]
        for row in rows
    ) and all(safe_checks)
    write_json(smoke_report_path(), {
        "status": "passed" if passed else "failed",
        "request_count": len(rows),
        "rows": rows,
        "security_boundary_passed": all(safe_checks),
        "model": MODEL,
        "structured_output": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    })
    print(json.dumps({"status": "passed" if passed else "failed", "requests": len(rows), "report": str(smoke_report_path())}, ensure_ascii=False))
    return passed


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    return float(statistics.quantiles(values, n=100, method="inclusive")[int(percentile_value) - 1]) if len(values) > 1 else float(values[0])


def aggregate(rows: list[dict[str, Any]], config: CredentialConfig) -> dict[str, Any]:
    answerable = [row for row in rows if row["question_type"] == "answerable"]
    unanswerable = [row for row in rows if row["question_type"] != "answerable"]
    latencies = [float(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    costs = [row.get("cost_usd") for row in rows if isinstance(row.get("cost_usd"), (int, float))]
    def avg(key: str, subset: list[dict[str, Any]] = rows) -> float:
        return sum(float(row.get(key, 0)) for row in subset) / len(subset) if subset else 0.0
    return {
        "query_count": len(rows),
        "answerable_count": len(answerable),
        "unanswerable_count": len(unanswerable),
        "answer_correctness": avg("answer_correct"),
        "required_fact_recall": avg("required_fact_recall", answerable),
        "citation_validity": avg("citation_valid"),
        "citation_coverage": avg("citation_coverage"),
        "citation_support": avg("citation_support"),
        "unsupported_claim_rate": avg("unsupported_claim"),
        "false_refusal_rate": sum(row["status"] == "insufficient_evidence" for row in answerable) / len(answerable) if answerable else 0.0,
        "unanswerable_abstention_rate": sum(row["status"] == "insufficient_evidence" for row in unanswerable) / len(unanswerable) if unanswerable else 0.0,
        "structured_output_rate": avg("schema_valid"),
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "total_latency_ms": sum(latencies),
        "input_tokens": sum((row.get("usage") or {}).get("input_tokens") or 0 for row in rows),
        "cached_tokens": sum((row.get("usage") or {}).get("cached_tokens") or 0 for row in rows),
        "reasoning_tokens": sum((row.get("usage") or {}).get("reasoning_tokens") or 0 for row in rows),
        "output_tokens": sum((row.get("usage") or {}).get("output_tokens") or 0 for row in rows),
        "cost_usd": sum(costs) if costs else None,
        "retry_count": sum(row.get("retry_count", 0) for row in rows),
        "api_error_count": sum(bool(row.get("failure_types")) and not row.get("schema_valid") for row in rows),
        "budget_limit_usd": config.max_cost_usd,
        "request_count": len(rows),
    }


def write_failures(rows: list[dict[str, Any]]) -> None:
    fields = ["query_id", "condition", "query", "question_type", "failure_types", "answer", "citations", "context_unit_ids", "schema_valid", "citation_valid"]
    with (ROUND_DIR / "failures.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            if row.get("failure_types"):
                writer.writerow({field: json.dumps(row.get(field), ensure_ascii=False) if isinstance(row.get(field), (list, dict)) else row.get(field) for field in fields})


def load_local_baselines() -> dict[tuple[str, str], dict[str, Any]]:
    baselines: dict[tuple[str, str], dict[str, Any]] = {}
    for row in load_jsonl(CONTEXT_RESULTS_PATH):
        if row.get("condition") in {"oracle_packet", "dense_packet"}:
            baselines[(row["query_id"], row["condition"])] = row
    if LOCAL_9B_RESULTS_PATH.exists():
        for row in load_jsonl(LOCAL_9B_RESULTS_PATH):
            if row.get("condition") in {"oracle_packet_9b", "dense_packet_9b"}:
                baselines[(row["query_id"], row["condition"])] = row
    return baselines


def write_comparison(rows: list[dict[str, Any]]) -> None:
    baselines = load_local_baselines()
    fields = ["query_id", "condition", "four_b_correct", "nine_b_correct", "mimo_correct", "category"]
    with (ROUND_DIR / "model_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            base4 = baselines.get((row["query_id"], row["condition"]), {})
            base9 = baselines.get((row["query_id"], row["condition"] + "_9b"), {})
            four = bool(base4.get("answer_correct"))
            nine = bool(base9.get("answer_correct"))
            mimo = bool(row.get("answer_correct"))
            if mimo and not four and not nine:
                category = "local_failed_mimo_correct"
            elif not mimo and not four and not nine:
                category = "three_failed"
            elif mimo and (not four or not nine):
                category = "mimo_improved"
            elif not mimo and (four or nine):
                category = "mimo_declined"
            else:
                category = "unchanged"
            writer.writerow({"query_id": row["query_id"], "condition": row["condition"], "four_b_correct": four, "nine_b_correct": nine, "mimo_correct": mimo, "category": category})


def write_inspection(rows: list[dict[str, Any]]) -> None:
    cards = []
    for row in rows:
        cards.append(
            "<article><h3>" + html.escape(row["query_id"] + " · " + row["condition"]) + "</h3>"
            + "<p><b>Query:</b> " + html.escape(row["query"]) + "</p>"
            + "<p><b>Status:</b> " + html.escape(str(row.get("status"))) + "</p>"
            + "<p><b>Answer:</b> " + html.escape(str(row.get("answer"))) + "</p>"
            + "<p><b>Citations:</b> " + html.escape(json.dumps(row.get("citations", []), ensure_ascii=False)) + "</p></article>"
        )
    content = "<!doctype html><meta charset='utf-8'><title>008 MiMo inspection</title><style>body{font-family:Segoe UI,Arial;margin:2rem}article{border:1px solid #ccc;border-radius:8px;padding:1rem;margin:1rem 0}article p{white-space:pre-wrap}</style>" + "".join(cards)
    (ROUND_DIR / "inspection.html").write_text(content, encoding="utf-8")


def run_full(config: CredentialConfig, dataset: list[dict[str, Any]], packets: dict[tuple[str, str], dict[str, Any]], system_prompt: str) -> int:
    smoke_report = json.loads(smoke_report_path().read_text(encoding="utf-8")) if smoke_report_path().exists() else None
    if not smoke_report or smoke_report.get("status") != "passed":
        if not run_smoke(config, dataset, packets, system_prompt):
            return 2
    result_path = ROUND_DIR / "cloud_generation_results.jsonl"
    rows = load_jsonl(result_path) if result_path.exists() else []
    processed = {(row.get("query_id"), row.get("condition")) for row in rows if row.get("phase") == "formal"}
    formal_requests = len(dataset) * len(FORMAL_CONDITIONS)
    remaining_requests = formal_requests - len(processed)
    if existing_attempts() + remaining_requests > config.max_requests:
        print(json.dumps({"status": "blocked", "reason": "request_budget_exhausted_before_formal"}, ensure_ascii=False))
        return 2
    for query_row in dataset:
        for condition, _ in FORMAL_CONDITIONS:
            if (query_row["query_id"], condition) in processed:
                continue
            packet = packets[(query_row["query_id"], condition)]
            payload = make_payload(system_prompt, query_row["query"], packet)
            response, info = http_request(config, payload, "formal", query_row["query_id"], condition)
            _, parsed, message = parse_content(response or {})
            response_model = (response or {}).get("model") if response else None
            row = evaluate_result(query_row, packet, parsed, response_model, info.get("usage", {}), info.get("latency_ms", 0), info.get("error"))
            row["phase"] = "formal"
            row["retry_count"] = info.get("retries", 0)
            if message.get("reasoning_content"):
                row["failure_types"] = list(dict.fromkeys(row["failure_types"] + ["reasoning_content_present"]))
            if message.get("tool_calls") or (response or {}).get("usage", {}).get("web_search_usage"):
                row["failure_types"] = list(dict.fromkeys(row["failure_types"] + ["tool_or_web_call_present"]))
            if response_model != MODEL:
                row["failure_types"] = list(dict.fromkeys(row["failure_types"] + ["response_model_mismatch"]))
            row["cost_usd"] = info.get("cost_usd")
            rows.append(row)
            append_jsonl(result_path, row)
    metrics = {"round": "008_cloud_generation_upper_bound", "model": MODEL, "conditions": {condition: aggregate([row for row in rows if row["condition"] == condition], config) for condition, _ in FORMAL_CONDITIONS}, "request_attempts": existing_attempts(), "budget_usd": config.max_cost_usd, "credential_source": config.credential_source, "structured_output": {"type": "json_object"}, "thinking": {"type": "disabled"}, "seed": None, "temperature": TEMPERATURE, "top_p": TOP_P}
    write_json(ROUND_DIR / "metrics.json", metrics)
    write_comparison(rows)
    write_failures(rows)
    write_inspection(rows)
    print(json.dumps({"status": "completed", "metrics": str(ROUND_DIR / "metrics.json"), "requests": existing_attempts()}, ensure_ascii=False))
    return 0


def preflight_payloads(dataset: list[dict[str, Any]], packets: dict[tuple[str, str], dict[str, Any]], system_prompt: str) -> None:
    for query_row in dataset:
        for condition, _ in FORMAL_CONDITIONS:
            make_payload(system_prompt, query_row["query"], packets[(query_row["query_id"], condition)])


def run_preflight() -> int:
    config = load_credentials(create_template=True)
    public = config.to_public()
    try:
        dataset, packets = load_fixed_inputs()
        system_prompt = extract_system_prompt()
        preflight_payloads(dataset, packets, system_prompt)
        public["fixed_inputs"] = {"dataset": str(DATASET_PATH), "query_count": len(dataset), "packet_conditions": [condition for condition, _ in FORMAL_CONDITIONS]}
        public["safety_boundary"] = "passed"
        public["cost_estimate"] = estimate_cost(dataset, packets, system_prompt, 66)
    except (OSError, RuntimeError, ValueError) as exc:
        public["status"] = "offline_preflight_failed"
        public["reason"] = str(exc)
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0 if public["status"] == "ready" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Round 8 MiMo cloud-generation evaluation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--smoke", action="store_true")
    group.add_argument("--full", action="store_true")
    args = parser.parse_args()

    if args.preflight:
        return run_preflight()
    config = load_credentials(create_template=True)
    try:
        dataset, packets = load_fixed_inputs()
        system_prompt = extract_system_prompt()
        preflight_payloads(dataset, packets, system_prompt)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "offline_preflight_failed", "reason": str(exc)}, ensure_ascii=False))
        return 2
    if config.status != "ready":
        print(json.dumps({"status": config.status, "credential_source": config.credential_source, "config_path": str(config.config_path), "issues": list(config.issues)}, ensure_ascii=False))
        return 2
    if args.smoke:
        return 0 if run_smoke(config, dataset, packets, system_prompt) else 2
    return run_full(config, dataset, packets, system_prompt)


if __name__ == "__main__":
    raise SystemExit(main())
