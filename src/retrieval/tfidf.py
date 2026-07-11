"""Deterministic TF-IDF retrieval over a small in-memory corpus."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


LOGGER = logging.getLogger(__name__)
WHITESPACE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize whitespace without changing lexical content."""
    return WHITESPACE.sub(" ", text).strip()


@dataclass(frozen=True)
class Document:
    document_id: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    rank: int
    document_id: str
    text: str
    score: float


def load_corpus(path: Path) -> list[Document]:
    """Load a JSONL corpus with document_id and text fields."""
    documents: list[Document] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            try:
                document_id = str(row["document_id"])
                text = str(row["text"])
            except KeyError as exc:
                raise ValueError(f"{path}:{line_number} missing field {exc}") from exc
            documents.append(Document(document_id=document_id, text=text))
    return documents


class TfidfRetriever:
    """Fit a fixed word-level TF-IDF index and return deterministic rankings."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            min_df=1,
            norm="l2",
            sublinear_tf=True,
            token_pattern=r"(?u)\b\w\w+\b",
        )
        self.documents: list[Document] = []
        self._matrix = None

    def fit(self, documents: Iterable[Document]) -> "TfidfRetriever":
        by_text: dict[str, Document] = {}
        for document in documents:
            normalized = normalize_text(document.text)
            if not normalized:
                LOGGER.warning("Skipping empty document %s", document.document_id)
                continue
            candidate = Document(str(document.document_id), normalized)
            existing = by_text.get(normalized)
            if existing is None or candidate.document_id < existing.document_id:
                by_text[normalized] = candidate

        self.documents = sorted(by_text.values(), key=lambda item: item.document_id)
        if not self.documents:
            raise ValueError("Cannot fit TF-IDF retriever on an empty corpus")

        self._matrix = self.vectorizer.fit_transform([item.text for item in self.documents])
        LOGGER.info(
            "Fitted TF-IDF index: documents=%d features=%d",
            len(self.documents),
            self._matrix.shape[1],
        )
        return self

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if self._matrix is None:
            raise RuntimeError("Call fit() before search()")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        normalized_query = normalize_text(query)
        if not normalized_query:
            LOGGER.warning("Empty query received; returning no results")
            return []

        query_vector = self.vectorizer.transform([normalized_query])
        scores = np.asarray((self._matrix @ query_vector.T).toarray()).ravel()
        ranked_indices = sorted(
            range(len(self.documents)),
            key=lambda index: (-float(scores[index]), self.documents[index].document_id),
        )[: min(top_k, len(self.documents))]
        results = [
            SearchResult(
                rank=rank,
                document_id=self.documents[index].document_id,
                text=self.documents[index].text,
                score=float(scores[index]),
            )
            for rank, index in enumerate(ranked_indices, start=1)
        ]
        LOGGER.debug("Retrieved query=%r top_k=%d", normalized_query[:80], top_k)
        return results
