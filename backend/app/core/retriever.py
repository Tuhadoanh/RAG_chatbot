# backend/app/core/retriever.py
import pickle
from typing import List
import numpy as np
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from rank_bm25 import BM25Okapi

class HybridRetriever:
    """
    Kết hợp FAISS (semantic) + BM25 (keyword) bằng Reciprocal Rank Fusion (RRF).
    
    RRF: score(d) = Σ 1/(k + rank_i(d))
    k=60 là giá trị mặc định từ paper gốc — giảm ảnh hưởng của rank đầu
    khi một hệ thống retrieval không chắc chắn.
    
    Ưu điểm so với weighted sum:
    - Không cần normalize score giữa 2 hệ thống (FAISS trả cosine, BM25 trả TF-IDF)
    - Robust hơn với outlier (1 kết quả rank 1 không thể dominate toàn bộ)
    """

    def __init__(
        self,
        vectorstore: FAISS,
        bm25_index_path: str,
        k: int = 5,
        rrf_k: int = 60,
        bm25_top_n: int = 20,   # BM25 lấy nhiều hơn rồi rerank, FAISS đã có score_threshold
    ):
        self.vectorstore = vectorstore
        self.k = k
        self.rrf_k = rrf_k
        self.bm25_top_n = bm25_top_n

        # Load BM25 index
        with open(bm25_index_path, "rb") as f:
            data = pickle.load(f)
        self.bm25: BM25Okapi = data["bm25"]
        self.bm25_docs: List[Document] = data["documents"]

    def retrieve(self, query: str, score_threshold: float = 0.5) -> List[Document]:
        """Trả về top-k documents sau khi fusion FAISS + BM25."""

        # ── FAISS semantic search ─────────────────────────────────────────────
        faiss_results = self.vectorstore.similarity_search_with_relevance_scores(
            query, k=self.k * 2  # Lấy dư để sau fusion vẫn đủ k
        )
        # Lọc theo score_threshold
        faiss_docs = [doc for doc, score in faiss_results if score >= score_threshold]

        # ── BM25 keyword search ───────────────────────────────────────────────
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_bm25_indices = np.argsort(bm25_scores)[::-1][:self.bm25_top_n]
        bm25_docs = [self.bm25_docs[i] for i in top_bm25_indices if bm25_scores[i] > 0]

        # ── Reciprocal Rank Fusion ────────────────────────────────────────────
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, Document] = {}

        def doc_id(doc: Document) -> str:
            """Dùng source + page + start_index làm key duy nhất."""
            m = doc.metadata
            return f"{m.get('source')}::{m.get('page')}::{m.get('start_index', 0)}"

        for rank, doc in enumerate(faiss_docs):
            did = doc_id(doc)
            rrf_scores[did] = rrf_scores.get(did, 0) + 1 / (self.rrf_k + rank + 1)
            doc_map[did] = doc

        for rank, doc in enumerate(bm25_docs):
            did = doc_id(doc)
            rrf_scores[did] = rrf_scores.get(did, 0) + 1 / (self.rrf_k + rank + 1)
            doc_map[did] = doc

        # Sort theo RRF score, lấy top-k
        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        return [doc_map[did] for did in sorted_ids[:self.k]]