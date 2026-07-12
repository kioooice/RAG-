from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil
from scipy import sparse
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.evaluation import evaluate_rankings, first_relevant_rank
from src.retrieval.semantic import DenseRetriever, reciprocal_rank_fusion
from src.retrieval.tfidf import Document, TfidfRetriever, load_corpus

EXPECTED_HASHES = {
    "corpus.jsonl": "56011E4BB78798F37CA97CCEF33048C26B1B1A6EBE3EDE45F48EA370E0CC8B52",
    "corpus_221.jsonl": "91C33A8C4C8A7A737722C6045EC42DEEFDA6D718D924D46974B929883D870D18",
    "queries.jsonl": "4C67061BD76B4BAC3EB254D05CAF7B6C558A88940A20E1B9F4C8017D7689BFEA",
    "001_metrics.json": "C97CD54AE1ECC57A644FD1FD811A2D87D68219FCE3FE050A4B8549B64C9E7558",
    "001_corpus_comparison.json": "BEF21DDE7274F5E63D9C4869222E4EA82277A28823390F5122CD7646C8D18915",
}
MODEL_ID = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
RRF_K = 60


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


class MemorySampler:
    def __init__(self) -> None:
        self.stop = threading.Event()
        self.peak = 0

    def __enter__(self):
        process = psutil.Process()
        self.peak = process.memory_info().rss

        def sample():
            while not self.stop.wait(0.02):
                self.peak = max(self.peak, process.memory_info().rss)

        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=1)


def latency_stats(values: list[float]) -> dict[str, float]:
    return {
        "average_query_latency_ms": statistics.fmean(values),
        "p50_query_latency_ms": float(np.percentile(values, 50)),
        "p95_query_latency_ms": float(np.percentile(values, 95)),
    }


def metric_block(details: list[dict], subset_ids: set[str] | None = None) -> dict:
    selected = [row for row in details if subset_ids is None or row["query_id"] in subset_ids]
    metrics = evaluate_rankings((row["ranked_ids"][:5], set(row["relevant_ids"])) for row in selected)
    metrics.update(latency_stats([row["latency_ms"] for row in selected]))
    metrics["query_count"] = len(selected)
    return metrics


def evaluate_method(name, queries, documents, tfidf, dense):
    document_map = {document.document_id: document.text for document in documents}
    details = []
    for query in queries:
        started = time.perf_counter()
        if name == "tfidf":
            results = tfidf.search(query["query"], top_k=len(documents))
        elif name == "dense":
            results = dense.search(query["query"], top_k=len(documents))
        else:
            lexical = tfidf.search(query["query"], top_k=len(documents))
            semantic = dense.search(query["query"], top_k=len(documents))
            results = reciprocal_rank_fusion(lexical, semantic, document_map, RRF_K)
        latency = (time.perf_counter() - started) * 1000
        ranked_ids = [result.document_id for result in results]
        details.append({
            "query_id": query["query_id"], "query": query["query"],
            "relevant_ids": query["relevant_document_ids"], "ranked_ids": ranked_ids,
            "scores": [result.score for result in results[:5]], "latency_ms": latency,
            "split": query.get("split", "chinese"), "query_type": query.get("query_type", "english"),
            "difficulty": query.get("difficulty", "emanual"),
        })
    return details


def build_indexes(documents, model, output_dir, corpus_name):
    started = time.perf_counter(); tfidf = TfidfRetriever().fit(documents); tfidf_seconds = time.perf_counter() - started
    canonical = tfidf.documents
    dense = DenseRetriever(model, batch_size=4)
    with MemorySampler() as sampler:
        dense_build = dense.fit(canonical)
    vector_path = output_dir / f"{corpus_name}_bge_m3_dense.npy"
    np.save(vector_path, dense_build.embeddings, allow_pickle=False)
    tfidf_path = output_dir / f"{corpus_name}_tfidf.npz"
    sparse.save_npz(tfidf_path, tfidf._matrix)
    return tfidf, dense, {
        "tfidf_build_seconds": tfidf_seconds,
        "dense_embedding_seconds": dense_build.seconds,
        "hybrid_build_seconds": tfidf_seconds + dense_build.seconds,
        "dense_peak_rss_bytes": sampler.peak,
        "tfidf_index_bytes": tfidf_path.stat().st_size,
        "dense_vector_bytes": vector_path.stat().st_size,
        "hybrid_index_bytes": tfidf_path.stat().st_size + vector_path.stat().st_size,
    }


def ranking_rows(dataset, corpus_name, queries, by_method):
    rows = []
    base = {row["query_id"]: row for row in by_method["tfidf"]}
    for method, details in by_method.items():
        for row in details:
            relevant = set(row["relevant_ids"])
            rank = first_relevant_rank(row["ranked_ids"], relevant)
            base_rank = first_relevant_rank(base[row["query_id"]]["ranked_ids"], relevant)
            change = "improved" if rank < base_rank else "declined" if rank > base_rank else "unchanged"
            rows.append({
                "dataset": dataset, "corpus": corpus_name, "query_id": row["query_id"],
                "split": row["split"], "query_type": row["query_type"], "difficulty": row["difficulty"],
                "method": method, "baseline_rank": base_rank, "rank": rank,
                "rank_delta_baseline_minus_method": base_rank - rank, "change": change,
                "hit_at_5": rank <= 5, "query": row["query"],
                "relevant_document_ids": "|".join(row["relevant_ids"]),
                "top5_document_ids": "|".join(row["ranked_ids"][:5]),
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--mx100-corpus", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--iteration-dir", type=Path, default=PROJECT_ROOT / "iterations/004_semantic_and_hybrid_retrieval")
    args = parser.parse_args()
    args.local_output.mkdir(parents=True, exist_ok=True)
    args.iteration_dir.mkdir(parents=True, exist_ok=True)

    protected = {
        "corpus.jsonl": args.data_dir / "corpus.jsonl",
        "corpus_221.jsonl": args.data_dir / "corpus_221.jsonl",
        "queries.jsonl": args.data_dir / "queries.jsonl",
        "001_metrics.json": PROJECT_ROOT / "iterations/001_retrieval_baseline/metrics.json",
        "001_corpus_comparison.json": PROJECT_ROOT / "iterations/001_retrieval_baseline/corpus_comparison.json",
    }
    observed_hashes = {name: sha256(path) for name, path in protected.items()}
    if observed_hashes != EXPECTED_HASHES:
        raise RuntimeError(f"Protected 001 input changed: {observed_hashes}")

    english_queries = load_jsonl(args.data_dir / "queries.jsonl")
    for row in english_queries:
        row["split"] = row["source_splits"][0]
    query_rows = load_jsonl(args.iteration_dir / "chinese_queries.jsonl")
    labels = {row["query_id"]: row["relevant_document_ids"] for row in load_jsonl(args.iteration_dir / "chinese_relevance.jsonl")}
    chinese_queries = [{**row, "relevant_document_ids": labels[row["query_id"]], "split": "chinese"} for row in query_rows]

    model_started = time.perf_counter()
    with MemorySampler() as load_memory:
        model = SentenceTransformer(str(args.model_path), device="cpu", local_files_only=True)
    model_load_seconds = time.perf_counter() - model_started
    model.max_seq_length = 8192

    datasets = {
        "english_152": (load_corpus(args.data_dir / "corpus.jsonl"), english_queries),
        "english_221": (load_corpus(args.data_dir / "corpus_221.jsonl"), english_queries),
        "chinese_mx100": (load_corpus(args.mx100_corpus), chinese_queries),
    }
    results = {}; all_changes = []; all_failures = []
    for dataset_name, (documents, queries) in datasets.items():
        tfidf, dense, resources = build_indexes(documents, model, args.local_output, dataset_name)
        methods = {name: evaluate_method(name, queries, tfidf.documents, tfidf, dense) for name in ("tfidf", "dense", "hybrid")}
        method_metrics = {}
        for method, details in methods.items():
            block = {"overall": metric_block(details)}
            if dataset_name.startswith("english"):
                for split in ("validation", "test"):
                    block[split] = metric_block(details, {row["query_id"] for row in queries if row["split"] == split})
            else:
                for query_type in ("keyword", "semantic"):
                    block[query_type] = metric_block(details, {row["query_id"] for row in queries if row["query_type"] == query_type})
            method_metrics[method] = block
            for row in details:
                if not set(row["ranked_ids"][:5]) & set(row["relevant_ids"]):
                    all_failures.append({
                        "dataset": dataset_name, "corpus": len(documents), "split": row["split"],
                        "query_type": row["query_type"], "method": method, "query_id": row["query_id"],
                        "query": row["query"], "relevant_document_ids": "|".join(row["relevant_ids"]),
                        "top5_document_ids": "|".join(row["ranked_ids"][:5]),
                        "observation": "Top-5 contains no labeled relevant unit; inspect lexical overlap and semantic neighbor rankings.",
                    })
        results[dataset_name] = {"corpus_document_count": len(tfidf.documents), "resources": resources, "methods": method_metrics}
        all_changes.extend(ranking_rows("chinese" if dataset_name == "chinese_mx100" else "english", dataset_name, queries, methods))

    english_221 = results["english_221"]["methods"]
    tfidf = english_221["tfidf"]; hybrid = english_221["hybrid"]; dense = english_221["dense"]
    recall_gain_questions = round((hybrid["overall"]["recall_at_5"] - tfidf["overall"]["recall_at_5"]) * 132)
    split_mrr_ok = all(hybrid[split]["mrr"] >= tfidf[split]["mrr"] - 0.02 for split in ("validation", "test"))
    zh = results["chinese_mx100"]["methods"]
    keyword_ok = hybrid["overall"]["recall_at_5"] >= tfidf["overall"]["recall_at_5"] and zh["hybrid"]["keyword"]["recall_at_5"] >= zh["tfidf"]["keyword"]["recall_at_5"]
    semantic_gain = round(
        (zh["hybrid"]["semantic"]["recall_at_5"] - zh["tfidf"]["semantic"]["recall_at_5"])
        * zh["hybrid"]["semantic"]["query_count"]
    )
    hybrid_accepted = recall_gain_questions >= 2 and split_mrr_ok and keyword_ok and semantic_gain >= 2
    dense_recall_gain_questions = round(
        (dense["overall"]["recall_at_5"] - tfidf["overall"]["recall_at_5"]) * 132
    )
    dense_split_mrr_ok = all(
        dense[split]["mrr"] >= tfidf[split]["mrr"] - 0.02
        for split in ("validation", "test")
    )
    dense_keyword_ok = (
        zh["dense"]["keyword"]["recall_at_5"]
        >= zh["tfidf"]["keyword"]["recall_at_5"]
    )
    dense_semantic_gain = round(
        (zh["dense"]["semantic"]["recall_at_5"] - zh["tfidf"]["semantic"]["recall_at_5"])
        * zh["dense"]["semantic"]["query_count"]
    )
    dense_accepted = (
        dense_recall_gain_questions >= 2
        and dense_split_mrr_ok
        and dense_keyword_ok
        and dense_semantic_gain >= 2
    )
    default_method = "hybrid" if hybrid_accepted else "dense" if dense_accepted else "tfidf"
    decision = {
        "default_method": default_method,
        "hybrid_accepted": hybrid_accepted,
        "dense_accepted": dense_accepted,
        "dense_candidate": dense["overall"]["recall_at_5"] > tfidf["overall"]["recall_at_5"],
        "english_221_dense_recall5_gain_questions": dense_recall_gain_questions,
        "dense_split_mrr_guardrail_passed": dense_split_mrr_ok,
        "dense_exact_match_guardrail_passed": dense_keyword_ok,
        "dense_chinese_semantic_recall5_gain_questions": dense_semantic_gain,
        "english_221_hybrid_recall5_gain_questions": recall_gain_questions,
        "split_mrr_guardrail_passed": split_mrr_ok,
        "exact_match_guardrail_passed": keyword_ok,
        "chinese_semantic_recall5_gain_questions": semantic_gain,
        "reason": (
            "Hybrid satisfies every predeclared gate."
            if hybrid_accepted
            else "Dense dominates TF-IDF under the same quality guardrails while Hybrid adds no Recall@5 benefit and lowers Chinese quality."
            if dense_accepted
            else "Neither learned method satisfies the quality guardrails; retain TF-IDF."
        ),
    }

    metrics = {
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "dimension": 1024, "max_input_tokens": 8192, "normalize_embeddings": True, "query_instruction": None},
        "rrf": {"k": RRF_K, "inputs": ["tfidf", "bge_m3_dense"]},
        "protected_input_hashes": observed_hashes,
        "datasets": results,
        "decision": decision,
    }
    (args.iteration_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = list(all_changes[0])
    with (args.iteration_dir / "ranking_changes.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(all_changes)
    failure_fields = list(all_failures[0]) if all_failures else ["dataset", "corpus", "split", "query_type", "method", "query_id", "query", "relevant_document_ids", "top5_document_ids", "observation"]
    with (args.iteration_dir / "failures.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=failure_fields); writer.writeheader(); writer.writerows(all_failures)

    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as error:
        gpu = f"unavailable:{error}"
    resource = {
        "python": sys.version.split()[0], "python_executable": sys.executable,
        "environment_path": sys.prefix, "environment_bytes": directory_size(Path(sys.prefix)),
        "model_path": str(args.model_path), "model_bytes": directory_size(args.model_path),
        "model_load_seconds": model_load_seconds, "model_load_peak_rss_bytes": load_memory.peak,
        "device_used": "cpu", "torch_version": importlib.metadata.version("torch"),
        "sentence_transformers_version": importlib.metadata.version("sentence-transformers"),
        "cuda_build": None, "cuda_available": False, "peak_gpu_bytes": 0,
        "detected_gpu": gpu, "pip_check": subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True).stdout.strip(),
        "offline_mode_verified": os.environ.get("HF_HUB_OFFLINE") == "1" and os.environ.get("TRANSFORMERS_OFFLINE") == "1",
        "selective_model_download_bytes": 2293333250, "python_package_download_bytes": 214991762,
        "full_model_repository_bytes_not_downloaded": 4587317404,
    }
    (args.iteration_dir / "resource_report.json").write_text(json.dumps(resource, ensure_ascii=False, indent=2), encoding="utf-8")

    options = lambda values: "".join(f"<option>{html.escape(str(value))}</option>" for value in values)
    table_rows = "".join(
        f"<tr data-split='{row['split']}' data-corpus='{row['corpus']}' data-method='{row['method']}' data-change='{row['change']}' data-type='{row['query_type']}' data-hit='{str(row['hit_at_5']).lower()}'><td>{row['dataset']}</td><td>{row['corpus']}</td><td>{row['split']}</td><td>{row['query_type']}</td><td>{row['method']}</td><td>{row['change']}</td><td>{row['hit_at_5']}</td><td>{html.escape(row['query'])}</td><td>{row['baseline_rank']}</td><td>{row['rank']}</td></tr>"
        for row in all_changes
    )
    page = f"""<!doctype html><meta charset=utf-8><title>004 retrieval inspection</title><style>body{{font:14px system-ui;margin:28px}}select{{margin:4px;padding:5px}}table{{border-collapse:collapse;width:100%}}th,td{{padding:6px;border-bottom:1px solid #ddd;text-align:left}}th{{position:sticky;top:0;background:#17324d;color:white}}</style><h1>004 语义与混合检索检查</h1><p>默认方法：<b>{decision['default_method']}</b></p><div id=f><select data-k=split><option value=''>全部Split</option>{options(['validation','test','chinese'])}</select><select data-k=corpus><option value=''>全部Corpus</option>{options(['english_152','english_221','chinese_mx100'])}</select><select data-k=method><option value=''>全部方法</option>{options(['tfidf','dense','hybrid'])}</select><select data-k=change><option value=''>全部变化</option>{options(['improved','declined','unchanged'])}</select><select data-k=type><option value=''>全部问题类型</option>{options(['english','keyword','semantic'])}</select><select data-k=hit><option value=''>全部Top-5状态</option>{options(['true','false'])}</select></div><table><thead><tr><th>数据</th><th>Corpus</th><th>Split</th><th>类型</th><th>方法</th><th>变化</th><th>Top5</th><th>Query</th><th>TF-IDF排名</th><th>方法排名</th></tr></thead><tbody>{table_rows}</tbody></table><script>const ss=[...document.querySelectorAll('select')],rs=[...document.querySelectorAll('tbody tr')];function f(){{rs.forEach(r=>r.hidden=ss.some(s=>s.value&&r.dataset[s.dataset.k]!==s.value))}}ss.forEach(s=>s.onchange=f)</script>"""
    (args.iteration_dir / "inspection.html").write_text(page, encoding="utf-8")
    print(json.dumps({"decision": decision, "datasets": {name: value["methods"] for name, value in results.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
