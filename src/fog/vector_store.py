"""
Fog Layer: Vector Store
FAISS-based vector store for document retrieval in the RAG pipeline.
"""

import json
import logging
import os
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A document stored in the vector store."""
    id: str
    content: str
    source: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    """A single search result from the vector store."""
    document: Document
    score: float
    rank: int


class VectorStore:
    """FAISS-based vector store for similarity search.

    Stores document embeddings and metadata for retrieval.
    Supports serialization to/from disk.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._index = None
        self._documents: list[Document] = []

    @property
    def index(self):
        """Lazy-initialize the FAISS index."""
        if self._index is None:
            try:
                import faiss
                self._index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine sim with normalized vectors)
                logger.info(f"Created FAISS index (dimension={self.dimension})")
            except ImportError:
                raise ImportError(
                    "faiss-cpu is required. Install with: pip install faiss-cpu"
                )
        return self._index

    @property
    def size(self) -> int:
        """Number of documents in the store."""
        return len(self._documents)

    def add_documents(
        self,
        documents: list[Document],
        embeddings: np.ndarray,
    ) -> None:
        """Add documents and their embeddings to the store.

        Args:
            documents: List of Document objects.
            embeddings: NumPy array of shape (len(documents), dimension).
        """
        if len(documents) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(documents)} documents but {len(embeddings)} embeddings"
            )

        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {embeddings.shape[1]}"
            )

        self.index.add(embeddings.astype(np.float32))
        self._documents.extend(documents)
        logger.info(f"Added {len(documents)} documents (total: {self.size})")

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search for the most similar documents.

        Args:
            query_embedding: 1D or 2D NumPy array of the query embedding.
            top_k: Number of results to return.

        Returns:
            List of SearchResult objects, sorted by score descending.
        """
        if self.size == 0:
            logger.warning("Vector store is empty, returning no results.")
            return []

        # Ensure 2D
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        k = min(top_k, self.size)
        scores, indices = self.index.search(query_embedding.astype(np.float32), k)

        results = []
        for rank, (idx, score) in enumerate(zip(indices[0], scores[0])):
            if idx < 0 or idx >= len(self._documents):
                continue
            results.append(SearchResult(
                document=self._documents[idx],
                score=float(score),
                rank=rank + 1,
            ))

        return results

    def save(self, index_path: str, metadata_path: str) -> None:
        """Save the index and metadata to disk.

        Args:
            index_path: Path to save the FAISS index.
            metadata_path: Path to save document metadata as JSON.
        """
        import faiss

        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_path), exist_ok=True)

        faiss.write_index(self.index, index_path)

        docs_data = [
            {
                "id": doc.id,
                "content": doc.content,
                "source": doc.source,
                "metadata": doc.metadata,
            }
            for doc in self._documents
        ]
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(docs_data, f, indent=2)

        logger.info(f"Saved index to {index_path} and metadata to {metadata_path}")

    def load(self, index_path: str, metadata_path: str) -> None:
        """Load the index and metadata from disk.

        Args:
            index_path: Path to the FAISS index file.
            metadata_path: Path to the document metadata JSON file.
        """
        import faiss

        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Index or metadata file not found at {index_path}")

        self._index = faiss.read_index(index_path)
        self.dimension = self._index.d

        with open(metadata_path, "r", encoding="utf-8") as f:
            docs_data = json.load(f)

        self._documents = [
            Document(
                id=d["id"],
                content=d["content"],
                source=d.get("source", ""),
                metadata=d.get("metadata", {}),
            )
            for d in docs_data
        ]

        logger.info(f"Loaded {self.size} documents from {index_path}")
