"""
Qdrant client wrapper for Synapse memory layers.

This module keeps the external Qdrant dependency behind a small API surface and
applies Thai-aware preprocessing before points are embedded and indexed.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Any, Sequence

# Default multilingual embedding model with good Thai support
DEFAULT_EMBEDDING_MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'

_logger = logging.getLogger(__name__)


class QdrantClient:
    """Small wrapper around ``qdrant-client`` with Synapse defaults."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        embedding_model: str | None = None,
        vector_size: int = 384,
        prefer_grpc: bool = False,
    ) -> None:
        env_vector_size = os.getenv('SYNAPSE_QDRANT_VECTOR_SIZE')
        if env_vector_size:
            try:
                vector_size = int(env_vector_size)
            except ValueError:
                pass

        self.url = url or os.getenv('QDRANT_URL', 'http://localhost:6333')
        self.api_key = api_key or os.getenv('QDRANT_API_KEY')
        self.embedding_model = embedding_model or os.getenv('SYNAPSE_QDRANT_EMBEDDING_MODEL')
        self.vector_size = vector_size
        self.prefer_grpc = prefer_grpc

        self._client: Any = None
        self._models: Any = None
        self._embedder: Any = None
        self._embedder_loaded = False
        self._preprocessor: Any = None

    def create_collection(
        self,
        collection_name: str,
        vector_size: int | None = None,
        recreate: bool = False,
    ) -> None:
        """Create a Qdrant collection if it does not already exist."""
        client = self._ensure_client()
        size = vector_size or self.vector_size

        if recreate:
            try:
                client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

        if self._collection_exists(collection_name):
            return

        client.create_collection(
            collection_name=collection_name,
            vectors_config=self._models.VectorParams(
                size=size,
                distance=self._models.Distance.COSINE,
            ),
        )

    def upsert(
        self,
        collection_name: str,
        points: Sequence[dict[str, Any]],
        wait: bool = True,
    ) -> None:
        """Upsert points into a collection."""
        if not points:
            return

        prepared_points: list[dict[str, Any]] = []
        vector_size = self.vector_size

        for point in points:
            point_id = point.get('id')
            if point_id is None:
                raise ValueError('Each Qdrant point must include an "id" field')

            payload = dict(point.get('payload') or {})
            text = str(
                point.get('text')
                or payload.get('text')
                or payload.get('summary')
                or payload.get('content')
                or point_id
            )
            indexed_text = self._preprocess_for_index(text)
            payload.setdefault('text', text)
            payload['indexed_text'] = indexed_text

            raw_vector = point.get('vector')
            vector = (
                [float(value) for value in raw_vector]
                if raw_vector is not None
                else self._embed_processed_text(indexed_text)
            )
            vector_size = len(vector)

            prepared_points.append(
                {
                    'id': str(point_id),
                    'vector': vector,
                    'payload': payload,
                }
            )

        self.create_collection(collection_name, vector_size=vector_size)

        qdrant_points = [
            self._models.PointStruct(
                id=point['id'],
                vector=point['vector'],
                payload=point['payload'],
            )
            for point in prepared_points
        ]

        client = self._ensure_client()
        client.upsert(collection_name=collection_name, points=qdrant_points, wait=wait)

    def search(
        self,
        collection_name: str,
        query_text: str | None = None,
        query_vector: Sequence[float] | None = None,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search a collection using a text query or vector."""
        if not self._collection_exists(collection_name):
            return []

        if query_vector is None:
            if not query_text:
                raise ValueError('query_text or query_vector is required for Qdrant search')
            query_vector = self._embed_processed_text(self._preprocess_for_query(query_text))

        client = self._ensure_client()
        query_filter = self._build_filter(filters) if filters else None
        raw_results: Any = None

        if hasattr(client, 'query_points'):
            try:
                result = client.query_points(
                    collection_name=collection_name,
                    query=list(query_vector),
                    query_filter=query_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                    with_vectors=False,
                )
                raw_results = getattr(result, 'points', result)
            except TypeError:
                raw_results = None

        if raw_results is None:
            raw_results = client.search(
                collection_name=collection_name,
                query_vector=list(query_vector),
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False,
            )

        return [
            {
                'id': str(getattr(result, 'id')),
                'score': float(getattr(result, 'score', 0.0) or 0.0),
                'payload': dict(getattr(result, 'payload', {}) or {}),
            }
            for result in raw_results
        ]

    def delete(
        self,
        collection_name: str,
        ids: Sequence[str] | None = None,
        filters: dict[str, Any] | None = None,
        wait: bool = True,
    ) -> None:
        """Delete points by id or payload filter."""
        if not ids and not filters:
            raise ValueError('ids or filters is required for Qdrant delete')

        if not self._collection_exists(collection_name):
            return

        client = self._ensure_client()

        if ids:
            selector = self._models.PointIdsList(points=[str(point_id) for point_id in ids])
        else:
            selector = self._models.FilterSelector(filter=self._build_filter(filters))

        client.delete(collection_name=collection_name, points_selector=selector, wait=wait)

    def _ensure_client(self) -> Any:
        """Lazily import and initialize the Qdrant SDK client."""
        if self._client is not None:
            return self._client

        try:
            from qdrant_client import QdrantClient as QdrantSdkClient
            from qdrant_client import models
        except ImportError as exc:
            raise RuntimeError(
                'qdrant-client is not installed. Install project dependencies before using Qdrant.'
            ) from exc

        self._models = models
        self._client = QdrantSdkClient(
            url=self.url,
            api_key=self.api_key,
            prefer_grpc=self.prefer_grpc,
        )
        return self._client

    def _collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists across Qdrant client versions."""
        client = self._ensure_client()

        if hasattr(client, 'collection_exists'):
            try:
                return bool(client.collection_exists(collection_name=collection_name))
            except TypeError:
                return bool(client.collection_exists(collection_name))

        try:
            client.get_collection(collection_name=collection_name)
            return True
        except Exception:
            return False

    def _ensure_preprocessor(self) -> Any | None:
        """Get the Synapse Thai-aware preprocessor if available."""
        if self._preprocessor is not None:
            return self._preprocessor if self._preprocessor is not False else None

        try:
            from synapse.nlp.preprocess import get_preprocessor

            self._preprocessor = get_preprocessor()
        except Exception:
            self._preprocessor = False

        return self._preprocessor if self._preprocessor is not False else None

    def _preprocess_for_index(self, text: str) -> str:
        """Normalize and tokenize text before embedding and indexing."""
        if not text:
            return ''

        preprocessor = self._ensure_preprocessor()
        if preprocessor is None:
            return text.strip()

        extraction = preprocessor.preprocess_for_extraction(text)
        tokens = preprocessor.tokenize_for_fts(extraction.processed)

        return ' '.join(part for part in [extraction.processed.strip(), tokens.strip()] if part)

    def _preprocess_for_query(self, text: str) -> str:
        """Preprocess a search query with Thai token retention."""
        if not text:
            return ''

        preprocessor = self._ensure_preprocessor()
        if preprocessor is None:
            return text.strip()

        return preprocessor.preprocess_for_search(text, keep_original_tokens=True).strip()

    def _embed_processed_text(self, text: str) -> list[float]:
        """Embed already-preprocessed text."""
        embedder = self._load_embedder()

        if embedder is None:
            return self._hash_embedding(text)

        vector = embedder.encode(text, normalize_embeddings=True)
        if hasattr(vector, 'tolist'):
            vector = vector.tolist()

        return [float(value) for value in vector]

    def _load_embedder(self) -> Any | None:
        """Load Sentence Transformers embedder.

        Uses configured model if provided, otherwise falls back to default
        multilingual model with Thai support.
        """
        if self._embedder_loaded:
            return self._embedder

        self._embedder_loaded = True

        model_name = (self.embedding_model or '').strip()
        using_default = False

        if not model_name:
            model_name = DEFAULT_EMBEDDING_MODEL
            using_default = True

        try:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(model_name)
            dimension = self._embedder.get_sentence_embedding_dimension()
            if dimension:
                self.vector_size = int(dimension)

            if using_default:
                _logger.warning(
                    "No embedding model configured, using default: %s. "
                    "Set SYNAPSE_QDRANT_EMBEDDING_MODEL env var for better performance.",
                    DEFAULT_EMBEDDING_MODEL
                )
        except Exception as exc:
            self._embedder = None
            _logger.warning(
                "Failed to load embedding model '%s': %s. "
                "Falling back to hash-based embeddings.",
                model_name, exc
            )

        return self._embedder

    def _hash_embedding(self, text: str) -> list[float]:
        """Deterministic fallback embedding used when no model backend is available."""
        if not text:
            return [0.0] * self.vector_size

        tokens = [token for token in text.split() if token]
        if not tokens:
            tokens = [text]

        vector = [0.0] * self.vector_size

        for token in tokens:
            digest = hashlib.blake2b(token.encode('utf-8'), digest_size=16).digest()
            index = int.from_bytes(digest[:4], 'big') % self.vector_size
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vector[index] += sign * weight

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0.0:
            return vector

        return [value / magnitude for value in vector]

    def _build_filter(self, filters: dict[str, Any]) -> Any | None:
        """Convert a Python dict into a Qdrant payload filter."""
        must: list[Any] = []
        must_not: list[Any] = []

        for field, value in filters.items():
            if value is None:
                continue

            if isinstance(value, dict):
                if {'gt', 'gte', 'lt', 'lte'} & set(value):
                    must.append(
                        self._models.FieldCondition(
                            key=field,
                            range=self._models.Range(
                                gt=value.get('gt'),
                                gte=value.get('gte'),
                                lt=value.get('lt'),
                                lte=value.get('lte'),
                            ),
                        )
                    )
                    continue

                if 'any' in value or 'match_any' in value:
                    any_values = value.get('any', value.get('match_any'))
                    must.append(
                        self._models.FieldCondition(
                            key=field,
                            match=self._models.MatchAny(any=list(any_values)),
                        )
                    )
                    continue

                if 'exclude' in value:
                    excluded = value['exclude']
                    if isinstance(excluded, (list, tuple, set)):
                        match = self._models.MatchAny(any=list(excluded))
                    else:
                        match = self._models.MatchValue(value=excluded)
                    must_not.append(self._models.FieldCondition(key=field, match=match))
                    continue

                if 'value' in value:
                    must.append(
                        self._models.FieldCondition(
                            key=field,
                            match=self._models.MatchValue(value=value['value']),
                        )
                    )
                    continue

            if isinstance(value, (list, tuple, set)):
                values = [item for item in value if item is not None]
                if not values:
                    continue
                must.append(
                    self._models.FieldCondition(
                        key=field,
                        match=self._models.MatchAny(any=values),
                    )
                )
                continue

            must.append(
                self._models.FieldCondition(
                    key=field,
                    match=self._models.MatchValue(value=value),
                )
            )

        if not must and not must_not:
            return None

        return self._models.Filter(
            must=must or None,
            must_not=must_not or None,
        )
