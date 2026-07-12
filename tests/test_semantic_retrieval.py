import unittest

import numpy as np

from src.retrieval.semantic import DenseRetriever, reciprocal_rank_fusion
from src.retrieval.tfidf import Document, SearchResult


class FakeEncoder:
    def encode(self, sentences, **kwargs):
        vectors = {"alpha": [1.0, 0.0], "beta": [0.0, 1.0], "find alpha": [1.0, 0.0]}
        return np.asarray([vectors[text] for text in sentences], dtype=np.float32)


class SemanticRetrievalTests(unittest.TestCase):
    def test_dense_ranking_and_determinism(self):
        retriever = DenseRetriever(FakeEncoder()).fit([Document("b", "beta"), Document("a", "alpha")])
        self.assertEqual(retriever.embeddings.shape, (2, 2))
        dense = DenseRetriever(FakeEncoder()); dense.fit([Document("b", "beta"), Document("a", "alpha")])
        self.assertEqual([item.document_id for item in dense.search("find alpha")], ["a", "b"])

    def test_fixed_rrf(self):
        lexical = [SearchResult(1, "a", "A", 1.0), SearchResult(2, "b", "B", 0.5)]
        dense = [SearchResult(1, "b", "B", 1.0), SearchResult(2, "a", "A", 0.5)]
        fused = reciprocal_rank_fusion(lexical, dense, {"a": "A", "b": "B"}, k=60)
        self.assertEqual([item.document_id for item in fused], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
