"""Stream RAGBench emanual/test and build deterministic local JSONL files."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
from pathlib import Path

from datasets import load_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "emanual_tfidf"
DATASET_ID = "galileo-ai/ragbench"
DATASET_REVISION = "97808f3e5fd16ede40bbff6c2949af8139b2eb7b"
CONFIG = "emanual"
SPLITS = ("validation", "test")
DEFAULT_SEED = 20260711
WHITESPACE = re.compile(r"\s+")
RELEVANT_KEY = re.compile(r"^(\d+)")


def normalize_text(text: str) -> str:
    return WHITESPACE.sub(" ", text).strip()


def stable_document_id(text: str) -> str:
    digest = hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()
    return f"doc_{digest[:16]}"


def relevant_indices(keys: list[str], document_count: int) -> list[int]:
    if not keys:
        return []
    indices = sorted(
        {
            int(match.group(1))
            for key in keys
            if (match := RELEVANT_KEY.match(str(key))) is not None
        }
    )
    if not indices or any(index >= document_count for index in indices):
        raise ValueError(
            f"Cannot map relevant keys {keys!r} to {document_count} documents"
        )
    return indices


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--query-count", type=int, default=132)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    source_rows: list[dict[str, object]] = []
    for split in SPLITS:
        stream = load_dataset(
            DATASET_ID,
            CONFIG,
            split=split,
            streaming=True,
            revision=DATASET_REVISION,
        )
        source_rows.extend({**row, "_source_split": split} for row in stream)

    grouped_rows: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in source_rows:
        key = (str(row["id"]), normalize_text(str(row["question"])))
        grouped_rows.setdefault(key, []).append(row)
    query_groups = [grouped_rows[key] for key in sorted(grouped_rows)]
    if args.query_count < 100:
        raise ValueError("query-count must be at least 100")
    if args.query_count > len(query_groups):
        raise ValueError(f"query-count exceeds unique queries: {len(query_groups)}")

    rng = random.Random(args.seed)
    rng.shuffle(query_groups)
    selected = query_groups[: args.query_count]

    corpus_by_id: dict[str, str] = {}
    query_rows: list[dict[str, object]] = []
    candidate_occurrences = 0
    source_records_without_relevant_mapping = 0
    for group in selected:
        first = group[0]
        question = normalize_text(str(first["question"]))
        candidate_document_ids: set[str] = set()
        relevant_document_ids: set[str] = set()
        relevant_sentence_keys: set[str] = set()
        reference_answers: set[str] = set()
        source_splits: set[str] = set()
        for row in group:
            documents = [normalize_text(str(text)) for text in row["documents"]]
            if not question or not documents or any(not text for text in documents):
                raise ValueError(f"Empty query or document in row {row.get('id')}")
            document_ids = [stable_document_id(text) for text in documents]
            for document_id, text in zip(document_ids, documents, strict=True):
                existing = corpus_by_id.setdefault(document_id, text)
                if existing != text:
                    raise ValueError(f"Stable ID collision for {document_id}")
            indices = relevant_indices(row["all_relevant_sentence_keys"], len(documents))
            candidate_document_ids.update(document_ids)
            relevant_document_ids.update(document_ids[index] for index in indices)
            if not indices:
                source_records_without_relevant_mapping += 1
            relevant_sentence_keys.update(str(key) for key in row["all_relevant_sentence_keys"])
            reference_answers.add(normalize_text(str(row["response"])))
            source_splits.add(str(row["_source_split"]))
            candidate_occurrences += len(documents)
        if not relevant_document_ids:
            raise ValueError(f"No relevant document mapping for query {first['id']}")
        query_rows.append(
            {
                "candidate_document_ids": sorted(candidate_document_ids),
                "query": question,
                "query_id": str(first["id"]),
                "reference_answer": sorted(reference_answers)[0],
                "reference_answers": sorted(reference_answers),
                "relevant_document_ids": sorted(relevant_document_ids),
                "relevant_sentence_keys": sorted(relevant_sentence_keys),
                "source_record_count": len(group),
                "source_splits": sorted(source_splits),
            }
        )

    corpus_rows = [
        {"document_id": document_id, "text": corpus_by_id[document_id]}
        for document_id in sorted(corpus_by_id)
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "corpus.jsonl", corpus_rows)
    write_jsonl(args.output_dir / "queries.jsonl", query_rows)
    metadata = {
        "candidate_document_occurrences": candidate_occurrences,
        "config": CONFIG,
        "corpus_document_count": len(corpus_rows),
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "duplicate_query_records_merged": len(source_rows) - len(query_groups),
        "query_count": len(query_rows),
        "seed": args.seed,
        "source_row_count": len(source_rows),
        "source_records_without_relevant_mapping": source_records_without_relevant_mapping,
        "split": "+".join(SPLITS),
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logging.info("Prepared %d queries and %d unique documents", len(query_rows), len(corpus_rows))
    print(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
