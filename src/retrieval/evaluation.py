"""Retrieval metrics with explicit any-relevant-document semantics."""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def first_relevant_rank(ranked_ids: Sequence[str], relevant_ids: set[str]) -> int | None:
    """Return the one-based rank of the first relevant document."""
    for rank, document_id in enumerate(ranked_ids, start=1):
        if document_id in relevant_ids:
            return rank
    return None


def evaluate_rankings(
    rankings: Iterable[tuple[Sequence[str], set[str]]],
    cutoffs: Sequence[int] = (1, 3, 5),
) -> dict[str, float | int]:
    """Average binary Recall@K and reciprocal rank across queries.

    With multiple relevant documents, Recall@K is one when any relevant document
    occurs in the first K results. MRR uses the first relevant document.
    """
    rows = list(rankings)
    if not rows:
        raise ValueError("At least one ranking is required")
    if any(not relevant for _, relevant in rows):
        raise ValueError("Every query must have at least one relevant document")

    totals = {cutoff: 0 for cutoff in cutoffs}
    reciprocal_rank_sum = 0.0
    misses_at_5 = 0
    for ranked_ids, relevant_ids in rows:
        rank = first_relevant_rank(ranked_ids, relevant_ids)
        for cutoff in cutoffs:
            totals[cutoff] += int(rank is not None and rank <= cutoff)
        reciprocal_rank_sum += 0.0 if rank is None else 1.0 / rank
        misses_at_5 += int(rank is None or rank > 5)

    count = len(rows)
    result: dict[str, float | int] = {
        f"recall_at_{cutoff}": totals[cutoff] / count for cutoff in cutoffs
    }
    result.update({"mrr": reciprocal_rank_sum / count, "misses_at_5": misses_at_5})
    return result
