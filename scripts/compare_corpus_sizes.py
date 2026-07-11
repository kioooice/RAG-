"""Compare the fixed TF-IDF baseline on 152 versus 221 public documents.

Only the ``documents`` field is read from emanual/train. Train questions,
generated responses, and relevance annotations are intentionally untouched.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import statistics
import sys
import time
from pathlib import Path

import numpy as np
from datasets import load_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.evaluation import evaluate_rankings, first_relevant_rank
from src.retrieval.tfidf import Document, TfidfRetriever, load_corpus, normalize_text


DATASET_ID = "galileo-ai/ragbench"
DATASET_REVISION = "97808f3e5fd16ede40bbff6c2949af8139b2eb7b"
CONFIG = "emanual"
TRAIN_SPLIT = "train"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "emanual_tfidf"
DEFAULT_ITERATION_DIR = PROJECT_ROOT / "iterations" / "001_retrieval_baseline"


def stable_document_id(text: str) -> str:
    digest = hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
    return f"doc_{digest[:16]}"


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, documents: list[Document]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for document in documents:
            row = {"document_id": document.document_id, "text": document.text}
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_expanded_corpus(baseline: list[Document]) -> tuple[list[Document], int]:
    by_id = {document.document_id: normalize_text(document.text) for document in baseline}
    train_occurrences = 0
    stream = load_dataset(
        DATASET_ID,
        CONFIG,
        split=TRAIN_SPLIT,
        streaming=True,
        revision=DATASET_REVISION,
    )
    for row in stream:
        # Deliberately access only train documents. No train query, response, or label is read.
        for raw_text in row["documents"]:
            text = normalize_text(str(raw_text))
            document_id = stable_document_id(text)
            existing = by_id.setdefault(document_id, text)
            if existing != text:
                raise ValueError(f"Stable ID collision for {document_id}")
            train_occurrences += 1
    documents = [Document(document_id, by_id[document_id]) for document_id in sorted(by_id)]
    if len(documents) != 221:
        raise ValueError(f"Expected 221 documents after train union, got {len(documents)}")
    return documents, train_occurrences


def evaluate_subset(
    retriever: TfidfRetriever, queries: list[dict[str, object]]
) -> tuple[dict[str, float | int], dict[str, list[str]]]:
    rankings: list[tuple[list[str], set[str]]] = []
    latencies_ms: list[float] = []
    top_five: dict[str, list[str]] = {}
    for query in queries:
        started = time.perf_counter()
        results = retriever.search(str(query["query"]), top_k=5)
        latencies_ms.append((time.perf_counter() - started) * 1000)
        ranked_ids = [result.document_id for result in results]
        relevant_ids = set(query["relevant_document_ids"])
        rankings.append((ranked_ids, relevant_ids))
        top_five[str(query["query_id"])] = ranked_ids
    metrics = evaluate_rankings(rankings)
    metrics["query_count"] = len(queries)
    metrics["average_query_latency_ms"] = statistics.fmean(latencies_ms)
    return metrics, top_five


def first_rank(retriever: TfidfRetriever, query: dict[str, object]) -> int:
    ranked_ids = [
        result.document_id
        for result in retriever.search(str(query["query"]), top_k=len(retriever.documents))
    ]
    rank = first_relevant_rank(ranked_ids, set(query["relevant_document_ids"]))
    if rank is None:
        raise ValueError(f"Relevant document missing from corpus for {query['query_id']}")
    return rank


def idf_comparison(
    baseline: TfidfRetriever, expanded: TfidfRetriever
) -> dict[str, int]:
    baseline_idf = dict(
        zip(baseline.vectorizer.get_feature_names_out(), baseline.vectorizer.idf_, strict=True)
    )
    expanded_idf = dict(
        zip(expanded.vectorizer.get_feature_names_out(), expanded.vectorizer.idf_, strict=True)
    )
    shared = set(baseline_idf) & set(expanded_idf)
    changed = sum(
        not np.isclose(baseline_idf[term], expanded_idf[term], rtol=0.0, atol=1e-12)
        for term in shared
    )
    return {
        "baseline_feature_count": len(baseline_idf),
        "expanded_feature_count": len(expanded_idf),
        "shared_feature_count": len(shared),
        "shared_features_with_changed_idf": changed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--iteration-dir", type=Path, default=DEFAULT_ITERATION_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    baseline_documents = load_corpus(args.data_dir / "corpus.jsonl")
    queries = load_jsonl(args.data_dir / "queries.jsonl")
    expanded_documents, train_occurrences = build_expanded_corpus(baseline_documents)
    write_jsonl(args.data_dir / "corpus_221.jsonl", expanded_documents)

    baseline = TfidfRetriever().fit(baseline_documents)
    expanded = TfidfRetriever().fit(expanded_documents)
    if len(baseline.documents) != 152:
        raise ValueError(f"Expected unchanged 152-document baseline, got {len(baseline.documents)}")

    variants: dict[str, dict[str, object]] = {
        "corpus_152": {"corpus_document_count": len(baseline.documents), "splits": {}},
        "corpus_221": {"corpus_document_count": len(expanded.documents), "splits": {}},
    }
    for split in ("validation", "test"):
        subset = [row for row in queries if row["source_splits"] == [split]]
        baseline_metrics, _ = evaluate_subset(baseline, subset)
        expanded_metrics, _ = evaluate_subset(expanded, subset)
        variants["corpus_152"]["splits"][split] = baseline_metrics
        variants["corpus_221"]["splits"][split] = expanded_metrics

    changes: list[dict[str, object]] = []
    summary = {"improved": 0, "declined": 0, "unchanged": 0}
    for query in sorted(queries, key=lambda row: str(row["query_id"])):
        rank_152 = first_rank(baseline, query)
        rank_221 = first_rank(expanded, query)
        if rank_221 < rank_152:
            change = "improved"
        elif rank_221 > rank_152:
            change = "declined"
        else:
            change = "unchanged"
        summary[change] += 1
        changes.append(
            {
                "query_id": query["query_id"],
                "split": query["source_splits"][0],
                "rank_152": rank_152,
                "rank_221": rank_221,
                "rank_delta_152_minus_221": rank_152 - rank_221,
                "change": change,
            }
        )

    baseline_recorded = json.loads(
        (args.iteration_dir / "metrics.json").read_text(encoding="utf-8")
    )
    combined_metrics = evaluate_rankings(
        (
            [result.document_id for result in baseline.search(str(row["query"]), top_k=5)],
            set(row["relevant_document_ids"]),
        )
        for row in queries
    )
    for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "misses_at_5"):
        if not np.isclose(combined_metrics[key], baseline_recorded[key]):
            raise ValueError(f"152-document baseline metric changed: {key}")

    output = {
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "evaluation_query_count": len(queries),
        "fixed_tfidf_config": baseline_recorded["tfidf_config"],
        "idf_comparison": idf_comparison(baseline, expanded),
        "ranking_change_summary": summary,
        "train_document_occurrences_read": train_occurrences,
        "train_fields_used": ["documents"],
        "variants": variants,
    }
    (args.iteration_dir / "corpus_comparison.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (args.iteration_dir / "corpus_ranking_changes.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(changes[0]))
        writer.writeheader()
        writer.writerows(changes)

    logging.info("Compared fixed TF-IDF on 152 and 221 documents")
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
