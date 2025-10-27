"""
Retrieval module for ECM RAG Chatbot.

Combines multiple search strategies:
1. Vector search (semantic) via Qdrant
2. BM25 (keyword) search for keyword matching
3. Reranking with CrossEncoder for relevance
4. ACL filtering based on user permissions

Usage:
  retriever = Retriever()
  results = retriever.hybrid_search(
      query="What is the timeline?",
      user=current_user,
      top_k=5
  )
"""

import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

# Local imports
from config import (
    QDRANT_URL,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    USE_RERANKER,
    RERANKER_MODEL,
    SEARCH_TOP_K,
    LOG_LEVEL,
)
from db import db, Document, Chunk, User

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# ========================
# Setup
# ========================

try:
    from qdrant_client import QdrantClient
except ImportError:
    logger.error("qdrant_client not installed")
    raise

qdrant_client = QdrantClient(url=QDRANT_URL)

# Initialize embedding model
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

# Initialize reranker (if enabled)
reranker = None
if USE_RERANKER:
    logger.info(f"Loading reranker model: {RERANKER_MODEL}")
    reranker = CrossEncoder(RERANKER_MODEL)


# ========================
# Data Classes
# ========================

@dataclass
class SearchResult:
    """A single search result."""
    chunk_id: int
    document_id: int
    filename: str
    department: str
    text: str
    score: float  # Relevance score (0-1)
    source_type: str  # "vector", "bm25", "reranked"


# ========================
# Core Retrieval Functions
# ========================

class Retriever:
    """Main retrieval interface."""

    def __init__(self):
        self.embedding_model = embedding_model
        self.reranker = reranker
        self.qdrant_client = qdrant_client
        self._bm25_index = None
        self._bm25_chunks = None
        self._load_bm25_index()

    def _load_bm25_index(self):
        """Load BM25 index from all chunks in database."""
        logger.info("Loading BM25 index...")
        session = db.get_session()
        chunks = session.query(Chunk).all()
        session.close()

        if not chunks:
            logger.warning("No chunks found for BM25 indexing")
            return

        # Tokenize all chunk texts
        tokenized_chunks = [chunk.text.lower().split() for chunk in chunks]
        self._bm25_index = BM25Okapi(tokenized_chunks)
        self._bm25_chunks = chunks
        logger.info(f"BM25 index loaded with {len(chunks)} chunks")

    def vector_search(self, query: str, top_k: int = SEARCH_TOP_K) -> List[SearchResult]:
        """
        Search using vector similarity (semantic search).
        
        Args:
            query: Search query string
            top_k: Number of results to return
        
        Returns:
            List of SearchResult objects
        """
        try:
            # Embed query
            query_embedding = self.embedding_model.encode(query, normalize_embeddings=True)

            # Search Qdrant
            search_results = self.qdrant_client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=query_embedding.tolist(),
                limit=top_k,
                with_payload=True,
            )

            # Convert to SearchResult
            results = []
            session = db.get_session()

            for scored_point in search_results:
                payload = scored_point.payload
                chunk_id = payload.get("chunk_id")
                doc_id = payload.get("doc_id")

                # Get document
                doc = session.query(Document).filter_by(id=doc_id).first()
                if not doc:
                    continue

                chunk = session.query(Chunk).filter_by(id=chunk_id).first()
                if not chunk:
                    continue

                result = SearchResult(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    filename=doc.filename,
                    department=doc.department or "",
                    text=chunk.text,
                    score=scored_point.score,
                    source_type="vector",
                )
                results.append(result)

            session.close()
            logger.debug(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def bm25_search(self, query: str, top_k: int = SEARCH_TOP_K) -> List[SearchResult]:
        """
        Search using BM25 (keyword search).
        
        Args:
            query: Search query string
            top_k: Number of results to return
        
        Returns:
            List of SearchResult objects
        """
        if not self._bm25_index or not self._bm25_chunks:
            logger.warning("BM25 index not loaded")
            return []

        try:
            # Tokenize query
            query_tokens = query.lower().split()

            # Get BM25 scores
            scores = self._bm25_index.get_scores(query_tokens)

            # Get top-k indices
            top_indices = np.argsort(scores)[::-1][:top_k]

            # Convert to SearchResult
            results = []
            session = db.get_session()

            for idx in top_indices:
                if scores[idx] < 0.1:  # Skip very low scores
                    break

                chunk = self._bm25_chunks[idx]
                doc = session.query(Document).filter_by(id=chunk.document_id).first()

                if not doc:
                    continue

                result = SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    filename=doc.filename,
                    department=doc.department or "",
                    text=chunk.text,
                    score=float(scores[idx]),
                    source_type="bm25",
                )
                results.append(result)

            session.close()
            logger.debug(f"BM25 search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []

    def rerank(self, query: str, candidates: List[SearchResult], top_k: int = 5) -> List[SearchResult]:
        """
        Rerank candidates using CrossEncoder.
        
        Args:
            query: Original search query
            candidates: List of SearchResult candidates
            top_k: Number of reranked results to return
        
        Returns:
            Reranked list of SearchResult objects
        """
        if not self.reranker or not candidates:
            return candidates[:top_k]

        try:
            # Prepare pairs for reranking
            pairs = [(query, result.text) for result in candidates]

            # Get reranker scores
            scores = self.reranker.predict(pairs)

            # Update scores
            for result, score in zip(candidates, scores):
                result.score = float(score)
                result.source_type = "reranked"

            # Sort by score and return top-k
            reranked = sorted(candidates, key=lambda x: x.score, reverse=True)[:top_k]
            logger.debug(f"Reranked {len(candidates)} candidates to {len(reranked)}")
            return reranked

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return candidates[:top_k]

    def filter_by_acl(self, results: List[SearchResult], user: Optional[User]) -> List[SearchResult]:
        """
        Filter results based on user ACLs.
        
        Args:
            results: List of SearchResult objects
            user: Current user (None = public access only)
        
        Returns:
            Filtered list of SearchResult objects
        """
        if not user:
            # No user = no access (unless documents are explicitly public)
            return []

        filtered = []
        session = db.get_session()

        for result in results:
            doc = session.query(Document).filter_by(id=result.document_id).first()
            if not doc:
                continue

            # Simple ACL logic: user can view if their dept matches document dept
            if doc.department and user.department:
                if doc.department.lower() == user.department.lower():
                    filtered.append(result)
                    continue

            # Could also check explicit ACL rules here
            # acl_rules = session.query(ACLRule).filter_by(
            #     user_id=user.id,
            #     document_id=doc.id,
            #     can_view=True
            # ).first()
            # if acl_rules:
            #     filtered.append(result)

        session.close()
        logger.debug(f"ACL filtering: {len(results)} → {len(filtered)} results")
        return filtered

    def hybrid_search(
        self,
        query: str,
        user: Optional[User] = None,
        top_k: int = SEARCH_TOP_K,
        use_reranker: Optional[bool] = None,
    ) -> List[SearchResult]:
        """
        Hybrid search combining vector + BM25 + reranking + ACL.
        
        Args:
            query: Search query
            user: Current user (for ACL filtering)
            top_k: Number of final results
            use_reranker: Override USE_RERANKER setting
        
        Returns:
            List of final SearchResult objects
        """
        logger.info(f"Hybrid search: '{query}' (user={user.username if user else 'None'})")

        # Get candidates from both vector and BM25
        vector_results = self.vector_search(query, top_k=top_k * 2)
        bm25_results = self.bm25_search(query, top_k=top_k * 2)

        # Merge and deduplicate
        combined = {}
        for result in vector_results + bm25_results:
            key = (result.chunk_id, result.document_id)
            if key not in combined:
                combined[key] = result
            else:
                # Average scores if from both sources
                combined[key].score = (combined[key].score + result.score) / 2

        candidates = list(combined.values())

        # Rerank if enabled
        should_rerank = use_reranker if use_reranker is not None else USE_RERANKER
        if should_rerank:
            candidates = self.rerank(query, candidates, top_k=top_k)

        # Filter by ACL
        final_results = self.filter_by_acl(candidates, user)

        # Ensure we return top_k
        final_results = sorted(final_results, key=lambda x: x.score, reverse=True)[:top_k]

        logger.info(f"Hybrid search returned {len(final_results)} results after filtering")
        return final_results


# ========================
# Standalone Functions
# ========================

def get_retriever() -> Retriever:
    """Get a global retriever instance."""
    if not hasattr(get_retriever, "_instance"):
        get_retriever._instance = Retriever()
    return get_retriever._instance


if __name__ == "__main__":
    # Quick test
    retriever = Retriever()
    results = retriever.hybrid_search("ECM replacement timeline")
    print(f"Found {len(results)} results:")
    for r in results:
        print(f"  - {r.filename}: {r.text[:100]}...")
