"""Evaluate the fixed TF-IDF baseline and write metrics plus observable failures."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import statistics
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.evaluation import evaluate_rankings, first_relevant_rank
from src.retrieval.tfidf import TfidfRetriever, load_corpus


DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "emanual_tfidf"
DEFAULT_ITERATION_DIR = PROJECT_ROOT / "iterations" / "001_retrieval_baseline"
TOKEN = re.compile(r"(?u)\b\w\w+\b")


def load_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def excerpt(text: str, limit: int = 260) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def visible_tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN.findall(text)}


def observe_failure(query: str, relevant_text: str, top1_text: str) -> str:
    query_tokens = visible_tokens(query)
    relevant_overlap = len(query_tokens & visible_tokens(relevant_text))
    top1_overlap = len(query_tokens & visible_tokens(top1_text))
    if relevant_overlap == 0:
        return "Query 与正确文档没有共享可见词项，存在明显用词差异。"
    if top1_overlap > relevant_overlap:
        return "相似但错误的文档与 Query 共享更多可见关键词。"
    if len(relevant_text) > 1.8 * max(1, len(top1_text)):
        return "正确文档明显更长，Query 词项在长文本中的权重较弱。"
    return "Query 与正确文档共享的可见词项较少，词法匹配信号不足。"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--iteration-dir", type=Path, default=DEFAULT_ITERATION_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    corpus = load_corpus(args.data_dir / "corpus.jsonl")
    queries = load_jsonl(args.data_dir / "queries.jsonl")
    metadata = json.loads((args.data_dir / "metadata.json").read_text(encoding="utf-8"))
    retriever = TfidfRetriever().fit(corpus)
    document_text = {document.document_id: document.text for document in retriever.documents}

    ranking_rows: list[tuple[list[str], set[str]]] = []
    details: list[dict[str, object]] = []
    latencies_ms: list[float] = []
    for query in queries:
        started = time.perf_counter()
        results = retriever.search(str(query["query"]), top_k=5)
        latencies_ms.append((time.perf_counter() - started) * 1000)
        ranked_ids = [result.document_id for result in results]
        relevant_ids = set(query["relevant_document_ids"])
        ranking_rows.append((ranked_ids, relevant_ids))
        rank = first_relevant_rank(ranked_ids, relevant_ids)
        details.append(
            {
                **query,
                "first_relevant_rank": rank,
                "results": [
                    {
                        "document_id": result.document_id,
                        "score": result.score,
                        "text": result.text,
                    }
                    for result in results
                ],
            }
        )

    metrics = evaluate_rankings(ranking_rows)
    metrics.update(
        {
            "average_document_length_chars": statistics.fmean(
                len(document.text) for document in retriever.documents
            ),
            "average_document_length_words": statistics.fmean(
                len(document.text.split()) for document in retriever.documents
            ),
            "average_query_latency_ms": statistics.fmean(latencies_ms),
            "candidate_document_occurrences": metadata["candidate_document_occurrences"],
            "config": metadata["config"],
            "corpus_document_count": len(retriever.documents),
            "dataset_id": metadata["dataset_id"],
            "dataset_revision": metadata["dataset_revision"],
            "duplicate_query_records_merged": metadata["duplicate_query_records_merged"],
            "query_count": len(queries),
            "seed": metadata["seed"],
            "source_records_without_relevant_mapping": metadata[
                "source_records_without_relevant_mapping"
            ],
            "source_row_count": metadata["source_row_count"],
            "split": metadata["split"],
            "tfidf_config": {
                "lowercase": True,
                "min_df": 1,
                "ngram_range": [1, 2],
                "norm": "l2",
                "sublinear_tf": True,
                "token_pattern": "(?u)\\b\\w\\w+\\b",
            },
        }
    )
    args.iteration_dir.mkdir(parents=True, exist_ok=True)
    (args.iteration_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.data_dir / "evaluation_details.json").write_text(
        json.dumps(details, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    misses = [row for row in details if row["first_relevant_rank"] is None]
    selected = list(misses)
    if len(selected) < 20:
        supplemental = sorted(
            (row for row in details if row not in misses),
            key=lambda row: (
                -(row["first_relevant_rank"] or 0),
                row["results"][0]["score"],
                row["query_id"],
            ),
        )
        selected.extend(supplemental[: 20 - len(selected)])

    fieldnames = [
        "query_id",
        "query",
        "relevant_document_ids",
        "relevant_document_excerpt",
        "top1_document_id",
        "top1_excerpt",
        "top1_score",
        "top5_document_ids",
        "failure_observation",
        "selection_type",
    ]
    with (args.iteration_dir / "failures.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in selected:
            relevant_ids = list(row["relevant_document_ids"])
            relevant_text = document_text[relevant_ids[0]]
            top1 = row["results"][0]
            writer.writerow(
                {
                    "query_id": row["query_id"],
                    "query": row["query"],
                    "relevant_document_ids": "|".join(relevant_ids),
                    "relevant_document_excerpt": excerpt(relevant_text),
                    "top1_document_id": top1["document_id"],
                    "top1_excerpt": excerpt(top1["text"]),
                    "top1_score": f"{top1['score']:.8f}",
                    "top5_document_ids": "|".join(
                        result["document_id"] for result in row["results"]
                    ),
                    "failure_observation": observe_failure(
                        str(row["query"]), relevant_text, str(top1["text"])
                    ),
                    "selection_type": (
                        "recall_at_5_miss"
                        if row["first_relevant_rank"] is None
                        else "low_rank_or_low_score_hit"
                    ),
                }
            )

    logging.info("Evaluated %d queries; Recall@5 misses=%d", len(queries), len(misses))
    print(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
