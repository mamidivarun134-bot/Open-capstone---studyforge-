"""
Lightweight, fully-local vector store built on TF-IDF + cosine similarity.

WHY TF-IDF instead of a neural embedding model or a hosted embeddings API:
this project targets zero-cost, zero-external-dependency operation for the
RAG layer so it can run entirely offline once installed (no API key, no
multi-gigabyte model download). TF-IDF is a legitimate, classical embedding
technique and is fully swappable: `embed_query` and `fit_corpus` are the
only two functions that would need to change to plug in sentence-transformers
or a hosted embeddings API instead (documented in docs/ARCHITECTURE.md).

Each user gets one TF-IDF vectorizer + sparse matrix, persisted to disk,
because vocabulary is only comparable within a single fitted vectorizer.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    row_index: int
    similarity: float


class UserVectorStore:
    """Persisted TF-IDF index scoped to a single user's corpus."""

    def __init__(self, store_dir: str, user_id: int):
        self.path = os.path.join(store_dir, f"user_{user_id}.joblib")
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None  # scipy sparse matrix, one row per chunk, in insertion order
        os.makedirs(store_dir, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            data = joblib.load(self.path)
            self.vectorizer = data["vectorizer"]
            self.matrix = data["matrix"]
        else:
            self.vectorizer = None
            self.matrix = None

    def save(self) -> None:
        joblib.dump({"vectorizer": self.vectorizer, "matrix": self.matrix}, self.path)

    def rebuild(self, all_chunk_texts: list[str]) -> None:
        """
        Refits the vectorizer over the FULL corpus (existing + new chunks).
        Simpler and more robust than incremental updates for a project of
        this scale; called once per document upload.
        """
        if not all_chunk_texts:
            self.vectorizer = None
            self.matrix = None
            return
        self.vectorizer = TfidfVectorizer(
            max_features=20000,
            ngram_range=(1, 2),
            stop_words="english",
            min_df=1,
        )
        self.matrix = self.vectorizer.fit_transform(all_chunk_texts)
        self.save()

    def search(self, query: str, top_k: int = 4) -> list[RetrievalResult]:
        if self.vectorizer is None or self.matrix is None or self.matrix.shape[0] == 0:
            return []
        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.matrix)[0]
        top_indices = np.argsort(sims)[::-1][:top_k]
        results = [RetrievalResult(row_index=int(i), similarity=float(sims[i])) for i in top_indices if sims[i] > 0]
        return results

    def cluster_topics(self, n_clusters: int) -> list[int]:
        """
        Unsupervised topic tagging: groups chunks into n_clusters topics via
        KMeans over their TF-IDF vectors. This is the ML component that
        automatically organizes a newly uploaded document into topics
        without requiring the student to label anything manually.

        Returns a list of cluster labels, one per row in self.matrix, in order.
        """
        if self.matrix is None or self.matrix.shape[0] == 0:
            return []
        effective_k = max(1, min(n_clusters, self.matrix.shape[0]))
        model = KMeans(n_clusters=effective_k, random_state=42, n_init=10)
        labels = model.fit_predict(self.matrix)
        return labels.tolist()

    def top_terms_for_rows(self, row_indices: list[int], top_n: int = 3) -> list[str]:
        """Extracts the highest-weighted terms across a set of rows, used to auto-name a topic cluster."""
        if self.vectorizer is None or self.matrix is None or not row_indices:
            return []
        sub_matrix = self.matrix[row_indices]
        mean_weights = np.asarray(sub_matrix.mean(axis=0)).ravel()
        top_indices = np.argsort(mean_weights)[::-1][:top_n]
        feature_names = self.vectorizer.get_feature_names_out()
        return [feature_names[i] for i in top_indices if mean_weights[i] > 0]
