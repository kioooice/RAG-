"""Query the prepared emanual TF-IDF corpus from PowerShell or another shell."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.tfidf import TfidfRetriever, load_corpus


DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "processed" / "emanual_tfidf"


def load_known_relevant(path: Path, query_id: str | None) -> set[str] | None:
    if query_id is None:
        return None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["query_id"] == query_id:
                return set(row["relevant_document_ids"])
    raise ValueError(f"Unknown query-id: {query_id}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--query-id", help="Show known relevance for an evaluation query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    relevant = load_known_relevant(args.data_dir / "queries.jsonl", args.query_id)
    retriever = TfidfRetriever().fit(load_corpus(args.data_dir / "corpus.jsonl"))
    results = retriever.search(args.query, top_k=args.top_k)
    if not results:
        print("Query 为空，没有检索结果。")
        return 0
    for result in results:
        marker = ""
        if relevant is not None:
            marker = " relevant=yes" if result.document_id in relevant else " relevant=no"
        text = result.text if len(result.text) <= 240 else result.text[:239].rstrip() + "…"
        print(
            f"{result.rank}. {result.document_id} score={result.score:.6f}{marker}\n"
            f"   {text}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
