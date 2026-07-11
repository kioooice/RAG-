from __future__ import annotations

import unittest

from src.retrieval.tfidf import Document, TfidfRetriever


class TfidfRetrieverTests(unittest.TestCase):
    def test_empty_query_returns_no_results(self) -> None:
        retriever = TfidfRetriever().fit([Document("doc_a", "alpha beta")])
        self.assertEqual(retriever.search("   "), [])

    def test_duplicate_text_is_deduplicated_deterministically(self) -> None:
        retriever = TfidfRetriever().fit(
            [Document("doc_z", "same text"), Document("doc_a", "same   text")]
        )
        self.assertEqual(len(retriever.documents), 1)
        self.assertEqual(retriever.documents[0].document_id, "doc_a")

    def test_top_k_returns_rank_id_text_and_score(self) -> None:
        retriever = TfidfRetriever().fit(
            [Document("doc_a", "television color settings"), Document("doc_b", "network setup")]
        )
        results = retriever.search("color settings", top_k=1)
        self.assertEqual(results[0].rank, 1)
        self.assertEqual(results[0].document_id, "doc_a")
        self.assertEqual(results[0].text, "television color settings")
        self.assertGreater(results[0].score, 0.0)


if __name__ == "__main__":
    unittest.main()
