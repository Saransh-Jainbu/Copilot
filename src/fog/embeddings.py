"""
Fog Layer: Embedding Generator
Generates text embeddings using SentenceTransformers for the RAG pipeline.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates embeddings using SentenceTransformers.

    Uses the all-MiniLM-L6-v2 model by default (384-dimensional vectors).
    Lazy-loads the model on first use to save memory.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load the SentenceTransformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("Embedding model loaded successfully.")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self.model.get_sentence_embedding_dimension()

    def encode(
        self,
        texts: list[str],
        batch_size: int = 64,
        show_progress: bool = False,
        normalize: bool = True,
    ) -> np.ndarray:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.
            batch_size: Batch size for encoding.
            show_progress: Show a progress bar.
            normalize: L2-normalize the embeddings.

        Returns:
            NumPy array of shape (len(texts), dimension).
        """
        if not texts:
            return np.array([])

        logger.info(f"Encoding {len(texts)} texts (batch_size={batch_size})")
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=normalize,
        )
        return np.array(embeddings, dtype=np.float32)

    def encode_single(self, text: str, normalize: bool = True) -> np.ndarray:
        """Encode a single text string.

        Args:
            text: The text to embed.
            normalize: L2-normalize the embedding.

        Returns:
            1D NumPy array of shape (dimension,).
        """
        return self.encode([text], normalize=normalize)[0]
