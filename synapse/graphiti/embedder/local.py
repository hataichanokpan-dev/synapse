"""
Local Embedder using sentence-transformers.

Supports multilingual models like multilingual-e5-small for Thai text.
No API key required - runs fully locally.
"""

import logging
from collections.abc import Iterable

from graphiti_core.embedder import EmbedderClient
from graphiti_core.embedder.openai import OpenAIEmbedderConfig
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Default model: multilingual-e5-small (384-dim, good Thai support)
DEFAULT_MODEL = "intfloat/multilingual-e5-small"
DEFAULT_DIMENSIONS = 384


class LocalEmbedderConfig(OpenAIEmbedderConfig):
    """Configuration for local sentence-transformers embedder."""

    model_name: str = DEFAULT_MODEL
    device: str | None = None  # auto-detect if None


class LocalEmbedder(EmbedderClient):
    """
    Local embedder using sentence-transformers.

    Uses E5 models which require prefix hints for optimal performance:
    - "query: " for queries
    - "passage: " for documents/passages

    For memory/knowledge graph use, we default to "passage: " prefix
    since most content is stored knowledge.
    """

    def __init__(self, config: LocalEmbedderConfig | None = None):
        if config is None:
            config = LocalEmbedderConfig()

        self.config = config
        self._model: SentenceTransformer | None = None

        logger.info(
            f"LocalEmbedder initialized: model={config.model_name}, dim={config.embedding_dim}"
        )

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the model on first use."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.config.model_name}")
            self._model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device,
            )
            logger.info(f"Model loaded successfully")
        return self._model

    def _add_prefix(self, text: str, is_query: bool = False) -> str:
        """Add E5 prefix for optimal embedding quality."""
        # E5 models work best with prefixes
        if self.config.model_name.startswith("intfloat/"):
            prefix = "query: " if is_query else "passage: "
            if not text.startswith(prefix):
                return f"{prefix}{text}"
        return text

    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        """Create embedding for a single input."""
        if isinstance(input_data, str):
            text = self._add_prefix(input_data)
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding[: self.config.embedding_dim].tolist()
        elif isinstance(input_data, list) and len(input_data) == 1 and isinstance(input_data[0], str):
            # Handle single-item list (common case from Graphiti)
            text = self._add_prefix(input_data[0])
            embedding = self.model.encode(text, normalize_embeddings=True)
            return embedding[: self.config.embedding_dim].tolist()
        elif isinstance(input_data, list) and all(isinstance(x, str) for x in input_data):
            # Handle list of strings - return first embedding
            texts = [self._add_prefix(t) for t in input_data]
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            return embeddings[0][: self.config.embedding_dim].tolist()
        else:
            raise NotImplementedError(f"LocalEmbedder doesn't support input type: {type(input_data)}")

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """Create embeddings for multiple inputs."""
        texts = [self._add_prefix(text) for text in input_data_list]
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [emb[: self.config.embedding_dim].tolist() for emb in embeddings]
