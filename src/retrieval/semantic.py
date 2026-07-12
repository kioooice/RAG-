"""Fixed dense retrieval and reciprocal-rank fusion for iteration 004."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Protocol

import numpy as np

from src.retrieval.tfidf import Document, SearchResult, normalize_text


class Encoder(Protocol):
    def encode(self, sentences, **kwargs): ...


def canonical_documents(documents: Iterable[Document]) -> list[Document]:
    by_text: dict[str, Document] = {}
    for document in documents:
        text = normalize_text(document.text)
        if not text:
            continue
        candidate = Document(str(document.document_id), text)
        current = by_text.get(text)
        if current is None or candidate.document_id < current.document_id:
            by_text[text] = candidate
    return sorted(by_text.values(), key=lambda item: item.document_id)


@dataclass
class DenseBuild:
    seconds: float
    embeddings: np.ndarray


class DenseRetriever:
    def __init__(self, encoder: Encoder, batch_size: int = 4) -> None:
        self.encoder = encoder
        self.batch_size = batch_size
        self.documents: list[Document] = []
        self.embeddings: np.ndarray | None = None

    def fit(self, documents: Iterable[Document]) -> DenseBuild:
        self.documents = canonical_documents(documents)
        started = time.perf_counter()
        matrix = self.encoder.encode(
            [document.text for document in self.documents],
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        seconds = time.perf_counter() - started
        self.embeddings = np.asarray(matrix, dtype=np.float32)
        return DenseBuild(seconds, self.embeddings)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if self.embeddings is None:
            raise RuntimeError("Call fit() before search()")
        clean = normalize_text(query)
        if not clean:
            return []
        vector = np.asarray(
            self.encoder.encode(
                [clean], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
            )[0],
            dtype=np.float32,
        )
        scores = self.embeddings @ vector
        indices = sorted(
            range(len(self.documents)),
            key=lambda index: (-float(scores[index]), self.documents[index].document_id),
        )[: min(top_k, len(self.documents))]
        return [
            SearchResult(rank, self.documents[index].document_id, self.documents[index].text, float(scores[index]))
            for rank, index in enumerate(indices, 1)
        ]


def reciprocal_rank_fusion(
    lexical: list[SearchResult], dense: list[SearchResult], documents: dict[str, str], k: int = 60
) -> list[SearchResult]:
    scores: dict[str, float] = {}
    for ranking in (lexical, dense):
        for result in ranking:
            scores[result.document_id] = scores.get(result.document_id, 0.0) + 1.0 / (k + result.rank)
    ordered = sorted(scores, key=lambda document_id: (-scores[document_id], document_id))
    return [SearchResult(rank, document_id, documents[document_id], scores[document_id]) for rank, document_id in enumerate(ordered, 1)]
