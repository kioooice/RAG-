from __future__ import annotations

import unittest

from src.retrieval.evaluation import evaluate_rankings


class RetrievalMetricTests(unittest.TestCase):
    def test_first_result_hit(self) -> None:
        metrics = evaluate_rankings([(["relevant", "other"], {"relevant"})])
        self.assertEqual(metrics["recall_at_1"], 1.0)
        self.assertEqual(metrics["recall_at_5"], 1.0)
        self.assertEqual(metrics["mrr"], 1.0)

    def test_hit_at_rank_five(self) -> None:
        ranking = ["d1", "d2", "d3", "d4", "relevant"]
        metrics = evaluate_rankings([(ranking, {"relevant"})])
        self.assertEqual(metrics["recall_at_1"], 0.0)
        self.assertEqual(metrics["recall_at_5"], 1.0)
        self.assertAlmostEqual(metrics["mrr"], 0.2)

    def test_complete_miss(self) -> None:
        metrics = evaluate_rankings([(["d1", "d2"], {"relevant"})])
        self.assertEqual(metrics["recall_at_1"], 0.0)
        self.assertEqual(metrics["recall_at_5"], 0.0)
        self.assertEqual(metrics["mrr"], 0.0)
        self.assertEqual(metrics["misses_at_5"], 1)

    def test_multiple_relevant_documents_use_first_hit(self) -> None:
        metrics = evaluate_rankings([(["d1", "relevant_b", "relevant_a"], {"relevant_a", "relevant_b"})])
        self.assertEqual(metrics["recall_at_1"], 0.0)
        self.assertEqual(metrics["recall_at_3"], 1.0)
        self.assertAlmostEqual(metrics["mrr"], 0.5)


if __name__ == "__main__":
    unittest.main()
