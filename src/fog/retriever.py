"""
Fog Layer: Retriever
Orchestrates embedding generation and FAISS search for the RAG pipeline.
"""

import logging
import re
from dataclasses import dataclass

from src.fog.embeddings import EmbeddingGenerator
from src.fog.vector_store import VectorStore, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Aggregated retrieval result for a query."""
    query: str
    results: list[SearchResult]
    total_candidates: int

    def to_context_string(self, max_results: int = 5) -> str:
        """Format retrieval results as a context string for the LLM.

        Args:
            max_results: Maximum number of results to include.

        Returns:
            Formatted context string.
        """
        if not self.results:
            return "No relevant documentation found."

        parts = []
        for r in self.results[:max_results]:
            parts.append(
                f"[Source: {r.document.source}] (Relevance: {r.score:.3f})\n"
                f"{r.document.content}"
            )
        return "\n\n---\n\n".join(parts)


class Retriever:
    """RAG retriever: embeds queries and searches the vector store.

    Combines EmbeddingGenerator and VectorStore into a single interface.
    """

    def __init__(
        self,
        embedding_generator: EmbeddingGenerator | None = None,
        vector_store: VectorStore | None = None,
        top_k: int = 5,
    ):
        self.embeddings = embedding_generator or EmbeddingGenerator()
        self.store = vector_store or VectorStore(dimension=384)
        self.top_k = top_k

    def retrieve(self, query: str, top_k: int | None = None, rerank_terms: list[str] | None = None) -> RetrievalResult:
        """Retrieve relevant documents for a query.

        Args:
            query: The search query text.
            top_k: Override for number of results.
            rerank_terms: Optional list of exact-match signal terms (e.g. image
                names, HTTP status codes, registry hosts) used to boost documents
                that contain these tokens above pure-semantic matches.

        Returns:
            RetrievalResult with ranked documents.
        """
        k = top_k or self.top_k

        # Retrieve a larger candidate pool when reranking so we can re-sort.
        fetch_k = k * 3 if rerank_terms else k

        # Generate query embedding
        query_embedding = self.embeddings.encode_single(query)

        # Search the vector store
        results = self.store.search(query_embedding, top_k=fetch_k)

        if rerank_terms:
            results = self._rerank(results, rerank_terms, top_k=k)

        logger.info(
            f"Retrieved {len(results)} results for query: '{query[:80]}...'"
        )

        return RetrievalResult(
            query=query,
            results=results,
            total_candidates=self.store.size,
        )

    def _rerank(
        self,
        results: list[SearchResult],
        terms: list[str],
        top_k: int,
        boost: float = 0.15,
    ) -> list[SearchResult]:
        """Re-rank FAISS results using token-overlap with provided signal terms.

        Each document whose content contains at least one signal term receives a
        ``boost`` additive bonus on top of the semantic score.  A second term hit
        adds ``boost / 2``, etc., so diminishing returns avoid over-weighting.

        Args:
            results:  Candidate list from FAISS (may be larger than ``top_k``).
            terms:    Signal terms such as image names, HTTP codes, registry hosts.
            top_k:    Final number of results to return after reranking.
            boost:    Score bonus for each distinct matched term.

        Returns:
            top_k SearchResult objects sorted by reranked score descending,
            with updated ``score`` and ``rank`` values.
        """
        if not terms or not results:
            return results[:top_k]

        # Pre-process terms to lowercase tokens for fast matching.
        term_patterns = [re.compile(re.escape(t.lower()), re.IGNORECASE) for t in terms if t]

        reranked = []
        for result in results:
            content = result.document.content.lower()
            bonus = 0.0
            decay = 1.0
            for pat in term_patterns:
                if pat.search(content):
                    bonus += boost * decay
                    decay *= 0.5  # Diminishing returns for each extra match.
            reranked.append((result.score + bonus, result))

        reranked.sort(key=lambda x: x[0], reverse=True)

        return [
            SearchResult(document=r.document, score=new_score, rank=rank + 1)
            for rank, (new_score, r) in enumerate(reranked[:top_k])
        ]

    def load_index(self, index_path: str, metadata_path: str) -> None:
        """Load a pre-built FAISS index.

        Args:
            index_path: Path to FAISS index file.
            metadata_path: Path to metadata JSON file.
        """
        self.store.load(index_path, metadata_path)
        logger.info(f"Loaded index with {self.store.size} documents")

    def build_index(
        self,
        documents: list[dict],
        batch_size: int = 64,
        save_path: tuple[str, str] | None = None,
    ) -> None:
        """Build a new FAISS index from documents.

        Args:
            documents: List of dicts with keys: id, content, source, metadata.
            batch_size: Batch size for embedding generation.
            save_path: Optional tuple of (index_path, metadata_path) to save.
        """
        from src.fog.vector_store import Document

        texts = [d["content"] for d in documents]
        embeddings = self.embeddings.encode(texts, batch_size=batch_size, show_progress=True)

        docs = [
            Document(
                id=d["id"],
                content=d["content"],
                source=d.get("source", ""),
                metadata=d.get("metadata", {}),
            )
            for d in documents
        ]

        self.store.add_documents(docs, embeddings)

        if save_path:
            self.store.save(save_path[0], save_path[1])

        logger.info(f"Built index with {self.store.size} documents")
