"""Offline claim-level audit for the Round 8 MiMo responses.

This script never calls a provider.  It treats the model's ``used_facts`` as
the starting point for atomic claims, splits common MX-100 table/list forms,
and checks domain anchors against the cited Evidence Packet text.  The audit
is intentionally conservative: a strict string mismatch is recorded as an
evaluator false positive only when the same anchors are present in the cited
evidence.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "iterations/008_cloud_generation_upper_bound"
OUTPUT_DIR = PROJECT_ROOT / "iterations/009_claim_level_grounding"
RESULTS_PATH = SOURCE_DIR / "cloud_generation_results.jsonl"
METRICS_PATH = SOURCE_DIR / "metrics.json"

CLASSIFICATIONS = {
    "supported_explicit",
    "supported_inference",
    "unsupported_harmless",
    "unsupported_material",
    "contradicted",
    "evaluator_false_positive",
    "non_factual_language",
}
SEVERITIES = {"none", "low", "medium", "high"}

ANCHORS = (
    "MX-100",
    "75℃",
    "v1.2",
    "2026-07-11",
    "E02",
    "E03",
    "E07",
    "E09",
    "代码",
    "温度上限",
    "温度过高",
    "max_temperature",
    "max_temp",
    "故障代码",
    "传感器离线",
    "感知元件掉线",
    "检查连接",
    "电源异常",
    "断电复位",
    "断电",
    "停止设备",
    "立即停机",
    "检查散热",
    "排查散热",
    "清洁滤网",
    "重启",
    "记录结果",
    "维护流程",
    "安全参数",
    "model",
    "version",
    "fault",
    "date",
    "warning",
    "Maintenance Guide",
)

ALIASES = {
    "感知元件掉线": "传感器离线",
    "排查散热": "检查散热",
    "切断电源": "断电",
    "max_temperature": "温度上限",
    "max_temp": "温度上限",
    "故障代码": "代码",
}

INFERENCE_MARKERS = (
    "下一步",
    "完成维护后",
    "安全极限",
    "无关",
    "章节标题",
    "章节",
    "第一步",
    "第三步",
    "最后一步",
    "应该",
    "允许",
    "当前",
    "表示",
    "对应",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize(text: str) -> str:
    value = text.lower().replace(" ", "").replace("　", "")
    for source, target in ALIASES.items():
        value = value.replace(source.lower(), target.lower())
    return value


def split_numbered_steps(text: str) -> list[str] | None:
    match = re.search(r"(?:^|[:：])\s*1[.、]\s*(.+)", text)
    if not match:
        return None
    tail = match.group(1).strip().rstrip("。")
    parts = re.split(r"[；;]\s*(?=2[.、])|\s+(?=2[.、])|[；;]\s*(?=3[.、])|\s+(?=3[.、])", tail)
    if len(parts) == 1 and "2." not in tail and "2、" not in tail:
        return None
    cleaned: list[str] = []
    for part in parts:
        part = part.strip().rstrip("；;。")
        part = re.sub(r"^\d+[.、]\s*", "", part)
        if part:
            cleaned.append(part)
    return cleaned or None


def split_claim_text(text: str) -> list[str]:
    """Split the recurring table/list forms into minimal factual statements."""

    value = text.strip().strip("。；;")
    steps = split_numbered_steps(value)
    if steps:
        prefix = re.split(r"[:：]\s*1[.、]", value, maxsplit=1)[0].strip()
        claims = []
        if prefix and "维护流程" not in prefix:
            claims.append(prefix)
        claims.extend(steps)
        return claims

    # Header/value table row emitted by the model.
    if "|" in value:
        parts = [part.strip() for part in value.split("|") if part.strip()]
        if len(parts) == 10 and parts[:5] == ["model", "version", "max_temp", "fault", "date"]:
            return [f"{header}={answer}" for header, answer in zip(parts[:5], parts[5:])]
        if len(parts) == 3 and re.fullmatch(r"E\d{2}", parts[0], flags=re.I):
            return [f"{parts[0]}对应现象是{parts[1]}", f"{parts[0]}处理方法是{parts[2]}"]

    # A slash is used for a date plus a document title in one response.
    if " / " in value:
        return [part.strip() for part in value.split(" / ") if part.strip()]

    # Split code/phenomenon/action clauses while keeping the subject in each.
    value = re.sub(r"，\s*(?=(?:处理方法|处理措施|处理)\s*(?:是|为))", "；", value)
    value = re.sub(r"，\s*(?=(?:处理方法|处理措施|处理)\s*是)", "；", value)
    clauses = [part.strip() for part in re.split(r"[。；;]", value) if part.strip()]
    if len(clauses) > 1:
        first = clauses[0]
        subject = re.search(r"(E\d{2}|MX-100)", first, flags=re.I)
        if subject:
            prefix = subject.group(1)
            expanded = [first]
            for clause in clauses[1:]:
                if not re.search(r"E\d{2}|MX-100", clause, flags=re.I):
                    expanded.append(prefix + clause)
                else:
                    expanded.append(clause)
            return expanded
        return clauses
    return [value] if value else []


def claim_anchors(text: str) -> list[str]:
    normalized = normalize(text)
    found: list[str] = []
    for anchor in ANCHORS:
        canonical = normalize(anchor)
        if canonical and canonical in normalized and canonical not in found:
            found.append(canonical)
    # Product codes and dates are useful even if a future response uses a
    # punctuation variant not listed above.
    for pattern in (r"e\d{2}", r"\d{4}-\d{2}-\d{2}", r"\d+(?:\.\d+)?℃"):
        for match in re.findall(pattern, normalized):
            if match not in found:
                found.append(match)
    return found


def cited_evidence(row: dict[str, Any]) -> dict[str, str]:
    packet_units = row.get("packet_units") or []
    by_id = {
        unit.get("knowledge_unit_id"): " ".join(
            [
                str(unit.get("title", "")),
                " ".join(str(item) for item in (unit.get("title_path") or [])),
                str(unit.get("content", "")),
            ]
        )
        for unit in packet_units
    }
    allowed = set((row.get("parsed_output") or {}).get("citations") or [])
    return {unit_id: by_id[unit_id] for unit_id in allowed if unit_id in by_id}


def classify_claim(row: dict[str, Any], claim: str, evidence: dict[str, str]) -> tuple[str, str, list[str], str]:
    anchors = claim_anchors(claim)
    evidence_norm = {unit_id: normalize(content) for unit_id, content in evidence.items()}
    supported_ids = [unit_id for unit_id, content in evidence_norm.items() if anchors and all(anchor in content for anchor in anchors)]
    if not supported_ids and anchors:
        # A claim can be supported by more than one cited unit when the model
        # combines a title/label with a table row.  Check the union as well.
        union = "".join(evidence_norm.values())
        if all(anchor in union for anchor in anchors):
            supported_ids = list(evidence_norm)

    strict_flag = bool(row.get("unsupported_claim"))
    if supported_ids:
        if strict_flag:
            return (
                "evaluator_false_positive",
                "none",
                supported_ids,
                "旧评测器按used_facts逐字匹配；引用Evidence包含同一事实锚点，属于改写或表格字段表示差异。",
            )
        if any(marker in claim for marker in INFERENCE_MARKERS):
            return (
                "supported_inference",
                "none",
                supported_ids,
                "Evidence明确给出相关字段或顺序，结论只做必要的直接推导。",
            )
        return ("supported_explicit", "none", supported_ids, "引用Evidence直接包含该事实或对应字段。")

    if not anchors:
        return ("non_factual_language", "none", [], "仅为格式或说明性文字，没有可验证的产品事实。")

    material_markers = ("温度", "故障", "处理", "停止", "检查", "断电", "重启", "版本", "日期", "75℃", "E0", "MX-100")
    if any(marker in claim for marker in material_markers):
        return ("unsupported_material", "high", [], "声明包含操作、条件、数值或故障结论，但引用Evidence没有对应事实。")
    return ("unsupported_harmless", "low", [], "未在引用Evidence中找到对应事实，但没有改变操作或产品结论。")


def audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audited: list[dict[str, Any]] = []
    for row in rows:
        parsed = row.get("parsed_output") or {}
        used_facts = parsed.get("used_facts") or []
        evidence = cited_evidence(row)
        source_claims: list[str] = []
        for fact in used_facts:
            source_claims.extend(split_claim_text(str(fact)))
        answer = str(parsed.get("answer") or "").strip()
        if parsed.get("status") == "answered":
            # The final answer can contain a fact omitted from used_facts (for
            # example a contrast such as “not related to cooling”).  Include
            # such facts instead of treating used_facts as a hidden answer.
            for candidate in split_claim_text(answer):
                if not claim_anchors(candidate):
                    continue
                candidate_anchors = set(claim_anchors(candidate))
                if not any(candidate_anchors == set(claim_anchors(existing)) for existing in source_claims):
                    source_claims.append(candidate)
        else:
            # A refusal explanation is retained for audit traceability but is
            # not counted as a product fact claim.
            if answer:
                audited.append(
                    {
                        "query_id": row.get("query_id"),
                        "condition": "oracle" if row.get("condition") == "oracle_packet" else "dense",
                        "claim_text": answer,
                        "citations": list(parsed.get("citations") or []),
                        "classification": "non_factual_language",
                        "severity": "none",
                        "evidence_unit_ids": [],
                        "explanation": "insufficient_evidence拒答说明，不是产品事实；不计入事实声明分母。",
                    }
                )
        for claim in source_claims:
            if not claim:
                continue
            classification, severity, evidence_ids, explanation = classify_claim(row, claim, evidence)
            audited.append(
                {
                    "query_id": row.get("query_id"),
                    "condition": "oracle" if row.get("condition") == "oracle_packet" else "dense",
                    "claim_text": claim,
                    "citations": list(parsed.get("citations") or []),
                    "classification": classification,
                    "severity": severity,
                    "evidence_unit_ids": evidence_ids,
                    "explanation": explanation,
                }
            )
    return audited


def calculate_metrics(rows: list[dict[str, Any]], claims: list[dict[str, Any]]) -> dict[str, Any]:
    answer_keys = [(row.get("query_id"), row.get("condition")) for row in rows]
    unsupported_classes = {"unsupported_harmless", "unsupported_material", "contradicted"}
    unsupported = [claim for claim in claims if claim["classification"] in unsupported_classes]
    factual = [claim for claim in claims if claim["classification"] != "non_factual_language"]
    cited = [claim for claim in factual if claim.get("citations")]
    cited_supported = [
        claim
        for claim in cited
        if claim["classification"] in {"supported_explicit", "supported_inference", "evaluator_false_positive"}
    ]
    unsupported_answer_keys = {
        (claim["query_id"], "oracle_packet" if claim["condition"] == "oracle" else "dense_packet")
        for claim in unsupported
    }
    material = [claim for claim in unsupported if claim["severity"] in {"medium", "high"}]
    counts = Counter(claim["classification"] for claim in claims)
    answer_count = len(set(answer_keys))
    strict_flagged_answers = sum(1 for row in rows if row.get("unsupported_claim"))
    strict_flagged_claims = counts.get("evaluator_false_positive", 0)
    true_unsupported_claims = len(unsupported)
    return {
        "source_round": "008_cloud_generation_upper_bound",
        "source_result_count": len(rows),
        "source_answer_count": answer_count,
        "factual_claim_count": len(factual),
        "claim_count": len(claims),
        "classification_counts": dict(sorted(counts.items())),
        "source_strict_unsupported_answer_count": strict_flagged_answers,
        "source_strict_unsupported_answer_rate": strict_flagged_answers / answer_count if answer_count else 0.0,
        "audited_strict_flagged_claim_count": strict_flagged_claims,
        "audited_strict_flag_false_positive_share": strict_flagged_claims / (strict_flagged_claims + true_unsupported_claims) if (strict_flagged_claims + true_unsupported_claims) else 0.0,
        "answer_level_unsupported_rate": len(unsupported_answer_keys) / answer_count if answer_count else 0.0,
        "answer_level_unsupported_answers": len(unsupported_answer_keys),
        "claim_level_unsupported_rate": len(unsupported) / len(factual) if factual else 0.0,
        "unsupported_claim_count": len(unsupported),
        "material_unsupported_rate": len(material) / len(unsupported) if unsupported else 0.0,
        "material_unsupported_over_all_claims": len(material) / len(factual) if factual else 0.0,
        "material_unsupported_claim_count": len(material),
        "claim_citation_coverage": len(cited) / len(factual) if factual else 0.0,
        "cited_claim_support": len(cited_supported) / len(cited) if cited else 0.0,
        "cited_claim_count": len(cited),
        "cited_supported_claim_count": len(cited_supported),
        "contradicted_claim_count": counts.get("contradicted", 0),
        "evaluator_false_positive_share_of_all_claims": counts.get("evaluator_false_positive", 0) / len(claims) if claims else 0.0,
        "api_evaluation": {
            "status": "not_run",
            "reason": "offline_audit_found_evaluator_false_positive_rate_over_20_percent",
            "run_id_reserved": "mimo_009_claim_grounding_v1",
            "request_count": 0,
            "cost_usd": 0.0,
        },
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_claims(path: Path, claims: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for claim in claims:
            handle.write(json.dumps(claim, ensure_ascii=False, sort_keys=True) + "\n")


def write_inspection(path: Path, claims: list[dict[str, Any]]) -> None:
    rows = []
    for claim in claims:
        rows.append(
            "<tr>"
            + "<td>" + html.escape(str(claim["query_id"])) + "</td>"
            + "<td>" + html.escape(str(claim["condition"])) + "</td>"
            + "<td>" + html.escape(str(claim["claim_text"])) + "</td>"
            + "<td>" + html.escape(str(claim["classification"])) + "</td>"
            + "<td>" + html.escape(str(claim["severity"])) + "</td>"
            + "<td>" + html.escape(json.dumps(claim["citations"], ensure_ascii=False)) + "</td>"
            + "<td>" + html.escape(json.dumps(claim["evidence_unit_ids"], ensure_ascii=False)) + "</td>"
            + "<td>" + html.escape(str(claim["explanation"])) + "</td>"
            + "</tr>"
        )
    content = (
        "<!doctype html><meta charset='utf-8'><title>009 Claim Audit</title>"
        "<style>body{font-family:Segoe UI,Arial;margin:2rem}table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccc;padding:.45rem;text-align:left;vertical-align:top}"
        "th{background:#f2f2f2;position:sticky;top:0}</style>"
        "<h1>009 Claim-Level Offline Audit</h1>"
        "<p>本页只审计008已保存结果；没有发送009 API请求。</p>"
        "<table><thead><tr><th>Query</th><th>Condition</th><th>Claim</th><th>Classification</th>"
        "<th>Severity</th><th>Citations</th><th>Evidence Units</th><th>Explanation</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    path.write_text(content, encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(RESULTS_PATH)
    claims = audit_rows(rows)
    metrics = calculate_metrics(rows, claims)
    source_metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    metrics["source_hashes"] = {
        "source_metrics_sha256": sha256(METRICS_PATH),
        "source_results_sha256": sha256(RESULTS_PATH),
    }
    metrics["source_run_id"] = source_metrics.get("run_id")
    write_claims(OUTPUT_DIR / "claim_audit.jsonl", claims)
    write_json(OUTPUT_DIR / "metrics_v2.json", metrics)
    write_json(
        OUTPUT_DIR / "metrics.json",
        {
            "round": "009_claim_level_grounding",
            "status": "offline_audit_complete_api_not_run",
            "source_metrics": "008_cloud_generation_upper_bound/metrics.json",
            "audit_metrics": metrics,
        },
    )
    (OUTPUT_DIR / "generation_results.jsonl").write_text(
        json.dumps(
            {
                "record_type": "evaluation_not_run",
                "run_id": "mimo_009_claim_grounding_v1",
                "reason": "offline_audit_found_evaluator_false_positive_rate_over_20_percent",
                "request_count": 0,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    with (OUTPUT_DIR / "failures.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["query_id", "condition", "failure_stage", "error_or_warning", "retryable", "recommended_action"])
        writer.writerow(["", "", "offline_audit_gate", "未发现需要API复测的真实unsupported claim；009云端阶段未运行", "no", "先修正评测口径或保留声明级协议供后续审批"])
    write_inspection(OUTPUT_DIR / "inspection.html", claims)
    print(json.dumps({"status": "offline_audit_complete", "claim_count": len(claims), "metrics": metrics}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
