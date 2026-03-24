"""
Layer 3: Semantic Memory

Principles, patterns, and learnings.
NORMAL DECAY - lambda = 0.01, half-life ~69 days

Storage:
- Graph: Entity nodes + Fact edges (via Graphiti)
- Vector: Qdrant for embeddings

This layer wraps Graphiti's functionality with:
- Decay scoring on retrieval
- Supersede pattern for outdated facts
- Layer classification for entities
- Thai NLP preprocessing for better extraction
"""

import asyncio
import json
import os
import logging
import random
import re
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import uuid4

from api.services.event_bus import FeedEventType
from synapse.graph_runtime import (
    bind_graphiti_client,
    load_graph_projection_runtime_config,
    normalize_graph_group_id,
)
from synapse.storage import QdrantClient
from synapse.graphiti.errors import (
    GraphitiWriteError,
    GraphitiConnectionError,
    GraphitiNotInitializedError,
)

from .types import (
    SynapseNode,
    SynapseEdge,
    SearchResult,
    MemoryLayer,
    EntityType,
    RelationType,
    utcnow,
)
from .decay import compute_decay_score, should_forget
from .semantic_store import SemanticProjectionStore, DEFAULT_DB_PATH

logger = logging.getLogger(__name__)
DEFAULT_COLLECTION_NAME = "semantic_memory"
_OUTBOX_POLL_INTERVAL_SECONDS = 30.0
_GRAPH_RATE_LIMIT_BACKOFFS = (300, 600, 1200, 2400, 3600)
_DEFAULT_OUTBOX_BACKENDS = ("vector", "graph")

# Environment variable to require Graphiti in production
# When true, Graphiti write failures will raise exceptions instead of silent warnings
_REQUIRE_GRAPHITI = os.environ.get("SYNAPSE_REQUIRE_GRAPHITI", "false").lower() == "true"


def _graphiti_enabled() -> bool:
    """Read Graphiti enablement dynamically for tests and local safe mode."""
    return os.environ.get("SYNAPSE_ENABLE_GRAPHITI", "true").lower() in {"1", "true", "yes", "on"}

# Lazy import for Thai NLP
_nlp_preprocessor = None


def _get_nlp_preprocessor():
    """Get NLP preprocessor (lazy import)."""
    global _nlp_preprocessor
    if _nlp_preprocessor is None:
        try:
            from synapse.nlp.preprocess import get_preprocessor
            _nlp_preprocessor = get_preprocessor()
        except ImportError:
            _nlp_preprocessor = False  # Mark as unavailable
    return _nlp_preprocessor if _nlp_preprocessor else None


def _sanitize_graph_group_id(group_id: Optional[str]) -> str:
    """Sanitize group IDs for Graphiti/FalkorDB compatibility."""
    return normalize_graph_group_id(group_id)


class SemanticManager:
    """
    Manager for Layer 3: Semantic Memory.

    Wraps Graphiti with decay scoring and supersede patterns.
    """

    def __init__(
        self,
        graphiti_client=None,
        vector_client: Optional[QdrantClient] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        db_path: Optional[Path] = None,
    ):
        """
        Initialize Semantic Memory Manager.

        Args:
            graphiti_client: Graphiti client instance (optional, lazy-loaded)
        """
        self._graphiti = graphiti_client
        self.vector_client = vector_client or QdrantClient()
        self.collection_name = collection_name
        self._initialized = False
        self._vector_warning_emitted = False
        self._runtime_config = load_graph_projection_runtime_config()
        self.store = SemanticProjectionStore(db_path or DEFAULT_DB_PATH)
        self._outbox_threads: Dict[str, threading.Thread] = {}
        self._outbox_wake_events: Dict[str, threading.Event] = {}
        self._outbox_stop_event = threading.Event()
        self._outbox_poll_interval = _OUTBOX_POLL_INTERVAL_SECONDS
        self._lease_owner = f"semantic-projector-{uuid4()}"
        self._event_bus = None
        self._backend_next_allowed_at: Dict[str, float] = {
            "graph": 0.0,
            "vector": 0.0,
        }
        try:
            self._app_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._app_loop = None

    def set_event_bus(self, event_bus: Any) -> None:
        """Attach the API event bus for graph projection lifecycle events."""
        self._event_bus = event_bus
        if self._app_loop is None:
            try:
                self._app_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._app_loop = None

    async def _ensure_graphiti(self, require: bool = False) -> bool:
        """Ensure Graphiti client is initialized when available."""
        if not _graphiti_enabled() and not require and not _REQUIRE_GRAPHITI:
            return False
        if self._graphiti is None:
            try:
                from graphiti_core import Graphiti

                self._graphiti = Graphiti()
                self._initialized = True
            except Exception as exc:
                if require:
                    raise GraphitiNotInitializedError(
                        "SemanticManager operations"
                    ) from exc
                return False
        return True

    async def verify_graphiti_connection(self) -> bool:
        """
        Verify Graphiti is connected and writable.

        This health check attempts a simple operation to confirm
        the graph database is accessible.

        Returns:
            True if Graphiti is available and working, False otherwise.
        """
        if self._graphiti is None:
            return False
        try:
            # Try a simple search to verify connection
            graphiti_client = self._bound_graphiti_client()
            if graphiti_client is None:
                return False
            await graphiti_client.search(query="__health_check__", num_results=1)
            return True
        except Exception as e:
            logger.warning(f"Graphiti connection check failed: {e}")
            return False

    def _handle_graphiti_error(self, operation: str, error: Exception, entity_name: str | None = None) -> None:
        """
        Handle Graphiti write errors consistently.

        If SYNAPSE_REQUIRE_GRAPHITI=true, raises GraphitiWriteError.
        Otherwise, logs a warning (backward compatible behavior).

        Args:
            operation: Name of the operation (e.g., 'add_entity', 'add_fact')
            error: The exception that occurred
            entity_name: Optional entity name for context

        Raises:
            GraphitiWriteError: If SYNAPSE_REQUIRE_GRAPHITI=true
        """
        if _REQUIRE_GRAPHITI:
            raise GraphitiWriteError(
                operation=operation,
                reason=str(error),
                entity_name=entity_name,
            ) from error
        else:
            # Backward compatible: silent warning
            logger.warning(f"Graphiti write failed during '{operation}' for '{entity_name}': {error}")

    def _warn_vector_issue(self, exc: Exception) -> None:
        """Log a single warning when Qdrant is unavailable."""
        if self._vector_warning_emitted:
            return

        logger.warning("Semantic memory Qdrant integration unavailable: %s", exc)
        self._vector_warning_emitted = True

    def _queue_outbox(self, target_backend: str, record_id: str, op_type: str, payload: Dict[str, Any]) -> None:
        """Enqueue a derived write and kick the worker."""
        operation_id = str(uuid4())
        dedupe_key = f"{op_type}:{record_id}:{target_backend}"
        self.store.enqueue_outbox(
            operation_id=operation_id,
            target_backend=target_backend,
            record_id=record_id,
            op_type=op_type,
            payload=payload,
            dedupe_key=dedupe_key,
            projector_version=self._runtime_config.projector_version,
        )
        if target_backend == "graph":
            self._emit_projection_event(
                FeedEventType.GRAPH_PROJECTION_QUEUED,
                summary="Graph projection queued",
                detail={
                    "backend": "graph",
                    "operation_id": operation_id,
                    "record_id": record_id,
                    "op_type": op_type,
                },
            )
        self._submit_outbox_worker(target_backend)

    def start_background_processing(self, poll_interval: float = _OUTBOX_POLL_INTERVAL_SECONDS) -> None:
        """Start persistent outbox processors for all known backends."""
        self._outbox_poll_interval = max(1.0, float(poll_interval))
        if self._outbox_stop_event.is_set():
            self._outbox_stop_event = threading.Event()
        for backend in _DEFAULT_OUTBOX_BACKENDS:
            self._submit_outbox_worker(backend)

    def stop_background_processing(self, join_timeout: float = 2.0) -> None:
        """Stop persistent outbox processors."""
        self._outbox_stop_event.set()
        for wake_event in self._outbox_wake_events.values():
            wake_event.set()

        current_thread = threading.current_thread()
        for backend, thread in list(self._outbox_threads.items()):
            if thread.is_alive() and thread is not current_thread:
                thread.join(timeout=join_timeout)
            self._outbox_threads.pop(backend, None)

        self._outbox_wake_events.clear()
        self._outbox_stop_event = threading.Event()

    def _submit_outbox_worker(self, target_backend: str) -> None:
        """Start or wake a persistent outbox worker for a backend."""
        wake_event = self._outbox_wake_events.setdefault(target_backend, threading.Event())
        thread = self._outbox_threads.get(target_backend)
        if thread is not None and thread.is_alive():
            wake_event.set()
            return
        thread = threading.Thread(
            target=self._outbox_worker_loop,
            args=(target_backend,),
            daemon=True,
            name=f"semantic-outbox-{target_backend}",
        )
        self._outbox_threads[target_backend] = thread
        thread.start()
        wake_event.set()

    def _graph_projection_group_id(self, group_id: Optional[str]) -> str:
        """Collapse projection writes into the canonical graph namespace."""
        _ = _sanitize_graph_group_id(group_id)
        return self._runtime_config.canonical_database

    def _bound_graphiti_client(self):
        """Return an isolated Graphiti client pinned to the canonical graph database."""
        return bind_graphiti_client(
            self._graphiti,
            database=self._runtime_config.canonical_database,
        )

    def _emit_projection_event(
        self,
        event_type: FeedEventType,
        *,
        summary: str,
        detail: Optional[Dict[str, Any]] = None,
        layer: str = MemoryLayer.SEMANTIC.value,
    ) -> None:
        """Emit projector lifecycle events on the API event bus when available."""
        if self._event_bus is None:
            return
        coro = self._event_bus.emit(
            event_type=event_type,
            summary=summary,
            layer=layer,
            detail=detail or {},
        )
        app_loop = self._app_loop
        if app_loop is not None and not app_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, app_loop)
            try:
                future.result(timeout=5)
            except Exception:
                logger.debug("Projection event emit timed out for %s", summary)
            return
        try:
            asyncio.run(coro)
        except Exception:
            logger.debug("Projection event emit failed for %s", summary)

    def _update_projector_state(self, backend: str, **fields: Any) -> Dict[str, Any]:
        return self.store.update_projector_state(backend, **fields)

    def _open_graph_circuit(self, reason: str, *, error_code: str, last_error: str) -> None:
        cooldown_until = datetime.fromtimestamp(
            utcnow().timestamp() + self._runtime_config.cooldown_seconds,
            tz=utcnow().tzinfo,
        ).isoformat()
        current = self.store.get_projector_state("graph")
        failure_streak = int(current.get("failure_streak") or 0) + 1
        updated = self._update_projector_state(
            "graph",
            circuit_state="paused_by_rate_limit",
            cooldown_until=cooldown_until,
            pause_reason=reason,
            last_error_code=error_code,
            provider_last_429_at=utcnow().isoformat() if error_code == "RATE_LIMIT" else current.get("provider_last_429_at"),
            last_error=last_error[:500],
            failure_streak=failure_streak,
        )
        self._emit_projection_event(
            FeedEventType.GRAPH_CIRCUIT_OPEN,
            summary="Graph projection paused by rate limit",
            detail={
                "backend": "graph",
                "reason": reason,
                "cooldown_until": updated.get("cooldown_until"),
                "last_error_code": error_code,
            },
        )

    def _close_graph_circuit(self, *, summary: str = "Graph projection resumed") -> None:
        updated = self._update_projector_state(
            "graph",
            circuit_state="closed",
            cooldown_until=None,
            pause_reason=None,
            failure_streak=0,
            last_error=None,
        )
        self._emit_projection_event(
            FeedEventType.GRAPH_CIRCUIT_CLOSED,
            summary=summary,
            detail={
                "backend": "graph",
                "circuit_state": updated.get("circuit_state"),
                "last_projected_at": updated.get("last_projected_at"),
            },
        )

    def pause_graph_projection(self) -> Dict[str, Any]:
        updated = self._update_projector_state(
            "graph",
            circuit_state="paused_manual",
            pause_reason="manual_maintenance",
            cooldown_until=None,
        )
        return {"affected": 1, "state": updated}

    def resume_graph_projection(self) -> Dict[str, Any]:
        self._close_graph_circuit(summary="Graph projection resumed manually")
        self._submit_outbox_worker("graph")
        return {"affected": 1, "state": self.store.get_projector_state("graph")}

    def replay_dead_letter_graph(self, *, dry_run: bool = False) -> Dict[str, Any]:
        count = self.store.count_outbox_rows(target_backend="graph", statuses=("dead_letter",))
        if dry_run:
            return {"affected": count, "dry_run": True}
        affected = self.store.requeue_outbox_rows(
            target_backend="graph",
            source_status="dead_letter",
            reset_retry_count=True,
        )
        if affected:
            self._submit_outbox_worker("graph")
        return {"affected": affected, "dry_run": False}

    def _outbox_worker_loop(self, target_backend: str) -> None:
        """Continuously drain due outbox work for one backend."""
        wake_event = self._outbox_wake_events.setdefault(target_backend, threading.Event())
        while not self._outbox_stop_event.is_set():
            processed = self._drain_outbox_backend(target_backend, limit=20)
            if processed > 0:
                continue
            wake_event.wait(timeout=self._outbox_poll_interval)
            wake_event.clear()

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Return True when an exception looks like a provider rate limit."""
        text = f"{type(exc).__name__}: {exc}".lower()
        return "429" in text or "rate limit" in text or "too many requests" in text

    def _classify_outbox_error(self, exc: Exception) -> Dict[str, str]:
        text = f"{type(exc).__name__}: {exc}".lower()
        if self._is_rate_limit_error(exc):
            return {"error_code": "RATE_LIMIT", "error_class": "transient"}
        if "timeout" in text or "timed out" in text or "deadline" in text:
            return {"error_code": "TIMEOUT", "error_class": "transient"}
        if "unavailable" in text or "connection" in text or "refused" in text:
            return {"error_code": "UPSTREAM_UNAVAILABLE", "error_class": "transient"}
        if isinstance(exc, (ValueError, TypeError, KeyError, json.JSONDecodeError)):
            return {"error_code": "INVALID_PAYLOAD", "error_class": "permanent"}
        if isinstance(exc, GraphitiNotInitializedError):
            return {"error_code": "GRAPHITI_UNAVAILABLE", "error_class": "transient"}
        return {"error_code": "UNKNOWN", "error_class": "transient"}

    def _calculate_outbox_retry_delay(self, target_backend: str, exc: Exception, retry_count: int) -> int:
        """Compute retry delay for an outbox failure."""
        if target_backend == "graph" and self._is_rate_limit_error(exc):
            base_delay = _GRAPH_RATE_LIMIT_BACKOFFS[min(max(retry_count - 1, 0), len(_GRAPH_RATE_LIMIT_BACKOFFS) - 1)]
            return base_delay + random.randint(0, 15)
        return min(300, max(15, 15 * (2 ** min(retry_count, 4))))

    def _graph_circuit_allows_work(self) -> bool:
        state = self.store.get_projector_state("graph")
        circuit_state = str(state.get("circuit_state") or "closed")
        if circuit_state == "paused_manual":
            return False
        if circuit_state != "paused_by_rate_limit":
            return True
        cooldown_until = self._parse_datetime(state.get("cooldown_until"))
        if cooldown_until is None or utcnow() >= cooldown_until:
            self._update_projector_state(
                "graph",
                circuit_state="half_open",
                pause_reason="canary_probe",
            )
            return True
        return False

    def _respect_projection_interval(self, target_backend: str) -> bool:
        if target_backend != "graph":
            return True
        now = time.monotonic()
        return now >= self._backend_next_allowed_at.get(target_backend, 0.0)

    def _mark_projection_attempt(self, target_backend: str) -> None:
        if target_backend != "graph":
            return
        self._backend_next_allowed_at[target_backend] = time.monotonic() + self._runtime_config.min_interval_seconds

    def _drain_outbox_backend(self, target_backend: str, limit: int = 20) -> int:
        """Lease and project due outbox rows for one backend."""
        self.store.release_expired_leases(
            target_backend=target_backend,
            lease_timeout_seconds=self._runtime_config.lease_timeout_seconds,
        )
        if target_backend == "graph" and not self._graph_circuit_allows_work():
            return 0
        if not self._respect_projection_interval(target_backend):
            return 0
        lease_limit = min(limit, self._runtime_config.max_inflight) if target_backend == "graph" else limit
        rows = self.store.lease_due_outbox(
            target_backend=target_backend,
            lease_owner=self._lease_owner,
            limit=max(1, lease_limit),
            lease_timeout_seconds=self._runtime_config.lease_timeout_seconds,
        )
        processed = 0
        for row in rows:
            operation_id = row["operation_id"]
            retry_count = int(row["retry_count"] or 0)
            payload = json.loads(row["payload_json"] or "{}")
            self._mark_projection_attempt(target_backend)
            try:
                if target_backend == "vector":
                    self._apply_vector_payload(payload)
                elif target_backend == "graph":
                    self._apply_graph_payload(payload)
                else:
                    continue
                self.store.mark_outbox_success(operation_id)
                if target_backend == "graph":
                    previous_state = str(self.store.get_projector_state("graph").get("circuit_state") or "closed")
                    self._update_projector_state(
                        "graph",
                        circuit_state="closed",
                        cooldown_until=None,
                        pause_reason=None,
                        last_projected_at=utcnow().isoformat(),
                        failure_streak=0,
                        last_error=None,
                    )
                    if previous_state == "half_open":
                        self._close_graph_circuit(summary="Graph projection canary succeeded")
                    self._emit_projection_event(
                        FeedEventType.GRAPH_PROJECTION_COMPLETED,
                        summary="Graph projection completed",
                        detail={
                            "backend": "graph",
                            "operation_id": operation_id,
                            "record_id": row["record_id"],
                            "op_type": row["op_type"],
                        },
                    )
            except Exception as exc:
                classification = self._classify_outbox_error(exc)
                delay_seconds = self._calculate_outbox_retry_delay(target_backend, exc, retry_count + 1)
                if target_backend == "vector":
                    self._warn_vector_issue(exc)
                    self.store.mark_outbox_retry(
                        operation_id,
                        str(exc),
                        retry_count + 1,
                        delay_seconds=delay_seconds,
                        error_code=classification["error_code"],
                        error_class=classification["error_class"],
                    )
                else:
                    logger.warning("Semantic graph outbox failure: %s", exc)
                    if classification["error_class"] == "permanent" or retry_count + 1 >= self._runtime_config.max_retries:
                        self.store.mark_outbox_dead_letter(
                            operation_id,
                            str(exc),
                            retry_count + 1,
                            error_code=classification["error_code"],
                            error_class=classification["error_class"],
                        )
                    else:
                        self.store.mark_outbox_retry(
                            operation_id,
                            str(exc),
                            retry_count + 1,
                            delay_seconds=delay_seconds,
                            error_code=classification["error_code"],
                            error_class=classification["error_class"],
                        )
                    current_state = self.store.get_projector_state("graph")
                    failure_streak = int(current_state.get("failure_streak") or 0) + 1
                    self._update_projector_state(
                        "graph",
                        last_error_code=classification["error_code"],
                        last_error=str(exc)[:500],
                        failure_streak=failure_streak,
                    )
                    if classification["error_code"] == "RATE_LIMIT":
                        self._open_graph_circuit(
                            "provider_rate_limit",
                            error_code=classification["error_code"],
                            last_error=str(exc),
                        )
                    self._emit_projection_event(
                        FeedEventType.GRAPH_PROJECTION_FAILED,
                        summary="Graph projection failed",
                        detail={
                            "backend": "graph",
                            "operation_id": operation_id,
                            "record_id": row["record_id"],
                            "op_type": row["op_type"],
                            "error_code": classification["error_code"],
                            "error_class": classification["error_class"],
                            "retry_count": retry_count + 1,
                        },
                    )
            processed += 1
        return processed

    def _apply_vector_payload(self, payload: Dict[str, Any]) -> None:
        """Apply a vector outbox payload."""
        node = SynapseNode(
            id=str(payload["id"]),
            type=EntityType(str(payload["entity_type"])),
            name=str(payload["name"]),
            summary=payload.get("summary"),
            memory_layer=MemoryLayer(str(payload.get("memory_layer", MemoryLayer.SEMANTIC.value))),
            confidence=float(payload.get("confidence", 0.7)),
            decay_score=float(payload.get("decay_score", 1.0)),
            access_count=int(payload.get("access_count", 0)),
            created_at=self._parse_datetime(payload.get("created_at")) or utcnow(),
            updated_at=self._parse_datetime(payload.get("updated_at")) or utcnow(),
            source_episode=payload.get("source_episode"),
            created_by=str(payload.get("created_by", "synapse")),
        )
        self._index_entity(node)

    def _apply_graph_payload(self, payload: Dict[str, Any]) -> None:
        """Apply a graph outbox payload."""
        if self._graphiti is None:
            raise GraphitiNotInitializedError("semantic_graph_outbox")
        op_type = str(payload.get("op_type") or "")
        if op_type in {"add_entity", "add_fact", "graph_event", "invalidate_fact", "update_entity"}:
            self._run_graph_coroutine(
                self._persist_graphiti_episode(
                    name=str(payload.get("graph_name") or f"entity_{payload.get('name', 'semantic')}"),
                    episode_body=str(payload.get("episode_body") or ""),
                    source_description=str(
                        payload.get("source_description")
                        or ("Fact" if op_type == "add_fact" else "Entity")
                    ),
                    reference_time=(
                        self._parse_datetime(payload.get("created_at"))
                        or self._parse_datetime(payload.get("valid_at"))
                        or utcnow()
                    ),
                    group_id=payload.get("group_id"),
                )
            )

    def _run_graph_coroutine(self, coro: Any) -> None:
        """Run Graphiti work on the app loop when available."""
        app_loop = self._app_loop
        if app_loop is not None and not app_loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, app_loop)
            future.result(timeout=60)
            return

        try:
            asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(coro)
            finally:
                loop.close()

    async def _persist_graphiti_episode(
        self,
        *,
        name: str,
        episode_body: str,
        source_description: str,
        reference_time: Optional[datetime] = None,
        group_id: Optional[str] = None,
    ) -> None:
        """Persist a semantic-side event to Graphiti with required arguments."""
        if self._graphiti is None:
            if _REQUIRE_GRAPHITI:
                raise GraphitiNotInitializedError("semantic_graph_persist")
            return

        graphiti_client = self._bound_graphiti_client()
        if graphiti_client is None:
            if _REQUIRE_GRAPHITI:
                raise GraphitiNotInitializedError("semantic_graph_persist")
            return

        await graphiti_client.add_episode(
            name=name,
            episode_body=episode_body,
            source_description=source_description,
            reference_time=reference_time or utcnow(),
            group_id=self._graph_projection_group_id(group_id),
        )

    def _index_entity(self, node: SynapseNode) -> bool:
        """Store entity text and metadata in Qdrant."""
        try:
            self.vector_client.upsert(
                collection_name=self.collection_name,
                points=[
                    {
                        "id": node.id,
                        "text": "\n".join(part for part in [node.name, node.summary or ""] if part),
                        "payload": {
                            "node_id": node.id,
                            "entity_type": node.type.value if hasattr(node.type, 'value') else node.type,
                            "name": node.name,
                            "summary": node.summary,
                            "memory_layer": node.memory_layer.value if hasattr(node.memory_layer, 'value') else node.memory_layer,
                            "confidence": node.confidence,
                            "decay_score": node.decay_score,
                            "access_count": node.access_count,
                            "created_at": node.created_at.isoformat(),
                            "updated_at": node.updated_at.isoformat(),
                            "expires_at": node.expires_at.isoformat() if node.expires_at else None,
                            "source_episode": node.source_episode,
                            "created_by": node.created_by,
                        },
                    }
                ],
            )
            return True
        except Exception as exc:
            self._warn_vector_issue(exc)
            return False

    def _payload_to_node(self, payload: Dict[str, Any]) -> Optional[SynapseNode]:
        """Convert a Qdrant payload into a SynapseNode."""
        node_id = payload.get("node_id")
        entity_type = payload.get("entity_type")
        name = payload.get("name")

        if node_id is None or entity_type is None or name is None:
            return None

        return SynapseNode(
            id=str(node_id),
            type=EntityType(str(entity_type)),
            name=str(name),
            summary=payload.get("summary"),
            memory_layer=MemoryLayer(str(payload.get("memory_layer", MemoryLayer.SEMANTIC.value))),
            confidence=float(payload.get("confidence", 0.7)),
            decay_score=float(payload.get("decay_score", 1.0)),
            access_count=int(payload.get("access_count", 0)),
            created_at=self._parse_datetime(payload.get("created_at")) or utcnow(),
            updated_at=self._parse_datetime(payload.get("updated_at")) or utcnow(),
            expires_at=self._parse_datetime(payload.get("expires_at")),
            source_episode=payload.get("source_episode"),
            created_by=str(payload.get("created_by", "synapse")),
        )

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO format datetime string."""
        if dt_str is None:
            return None

        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'

        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    def fetch_lexical_candidates(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch lexical semantic candidates from SQLite projection."""
        return self.store.fetch_lexical_candidates(query=query, limit=limit)

    def fetch_vector_candidates(
        self,
        query: str,
        limit: int = 20,
        embedding_cache: Any = None,
    ) -> List[Dict[str, Any]]:
        """Fetch vector semantic candidates from Qdrant."""
        try:
            results = self.vector_client.search(
                collection_name=self.collection_name,
                query_text=query,
                limit=max(limit, 1),
            )
        except Exception as exc:
            self._warn_vector_issue(exc)
            return []

        candidates: List[Dict[str, Any]] = []
        for rank, result in enumerate(results, start=1):
            node = self._payload_to_node(result.get("payload") or {})
            if node is None:
                node = self.store.get_node(str(result.get("id")))
            if node is None:
                continue
            indexed_text = self.store.fetch_lexical_candidates(node.name, limit=1)
            payload = {
                "uuid": node.id,
                "layer": MemoryLayer.SEMANTIC.value,
                "name": node.name,
                "content": node.summary or "",
                "metadata": {
                    "entity_type": node.type.value if hasattr(node.type, "value") else node.type,
                    "confidence": node.confidence,
                    "source_episode": node.source_episode,
                },
                "source": "semantic",
                "indexed_text": indexed_text[0]["payload"]["indexed_text"] if indexed_text else f"{node.name} {node.summary or ''}",
            }
            candidates.append(
                {
                    "record_id": node.id,
                    "layer": MemoryLayer.SEMANTIC,
                    "backend": "vector",
                    "backend_score": max(0.0, min(1.0, float(result.get("score", 0.0)))),
                    "rank": rank,
                    "exact_match": query.lower() in node.name.lower() or query.lower() in (node.summary or "").lower(),
                    "matched_terms": query.split(),
                    "match_reasons": ["vector_similarity"],
                    "freshness": max(0.0, min(1.0, node.decay_score)),
                    "usage_signal": min(1.0, node.access_count / 10.0),
                    "payload": payload,
                }
            )
        return candidates

    async def fetch_graph_candidates(
        self,
        query: str,
        limit: int = 15,
        *,
        seed_ids: Optional[List[str]] = None,
        query_type: str = "mixed",
    ) -> List[Dict[str, Any]]:
        """Fetch graph-derived semantic candidates."""
        graphiti_client = self._bound_graphiti_client()
        driver = getattr(graphiti_client, "driver", None) or getattr(graphiti_client, "_driver", None)
        if driver is None:
            return []

        seed_ids = [seed_id for seed_id in (seed_ids or []) if seed_id]
        records = []
        if seed_ids:
            try:
                records, _, _ = await driver.execute_query(
                    """
                    MATCH (n)-[e]-(m)
                    WHERE n.uuid IN $seed_ids OR m.uuid IN $seed_ids
                    RETURN COALESCE(e.uuid, n.uuid, m.uuid) AS uuid,
                           COALESCE(e.fact, e.name, '') AS fact,
                           COALESCE(e.name, 'RELATED_TO') AS relation,
                           n.uuid AS source_id,
                           m.uuid AS target_id,
                           COALESCE(n.name, n.uuid) AS source_name,
                           COALESCE(m.name, m.uuid) AS target_name,
                           COALESCE(e.created_at, n.created_at, m.created_at) AS created_at
                    LIMIT $limit
                    """,
                    seed_ids=seed_ids,
                    limit=limit,
                )
            except Exception as exc:
                logger.debug("Seeded graph fetch failed: %s", exc)
                records = []

        if not records and graphiti_client is not None:
            try:
                graph_results = await graphiti_client.search(query=query, num_results=limit)
            except Exception as exc:
                logger.debug("Graphiti search failed: %s", exc)
                graph_results = []

            converted: List[Dict[str, Any]] = []
            for rank, edge in enumerate(graph_results, start=1):
                fact = getattr(edge, "fact", "") or str(edge)
                source_id = getattr(edge, "source_node_uuid", None)
                target_id = getattr(edge, "target_node_uuid", None)
                converted.append(
                    {
                        "record_id": str(getattr(edge, "uuid", f"graph:{rank}:{source_id}:{target_id}")),
                        "layer": MemoryLayer.SEMANTIC,
                        "backend": "graph",
                        "backend_score": 1.0,
                        "rank": rank,
                        "exact_match": query.lower() in fact.lower(),
                        "matched_terms": query.split(),
                        "match_reasons": ["graph_search"],
                        "freshness": 1.0,
                        "usage_signal": 0.5,
                        "path": [str(source_id or "source"), fact[:80], str(target_id or "target")],
                        "payload": {
                            "uuid": str(getattr(edge, "uuid", f"graph:{rank}")),
                            "layer": MemoryLayer.SEMANTIC.value,
                            "name": fact[:80] or "Graph fact",
                            "content": fact,
                            "metadata": {
                                "source_id": source_id,
                                "target_id": target_id,
                            },
                            "source": "graph",
                            "indexed_text": fact,
                        },
                    }
                )
            return converted

        results: List[Dict[str, Any]] = []
        relational_boost = 1.0 if query_type == "relational" else 0.6
        for rank, record in enumerate(records, start=1):
            fact = record.get("fact") or f"{record.get('source_name')} {record.get('relation')} {record.get('target_name')}"
            results.append(
                {
                    "record_id": str(record.get("uuid") or f"graph:{rank}"),
                    "layer": MemoryLayer.SEMANTIC,
                    "backend": "graph",
                    "backend_score": min(1.0, relational_boost),
                    "rank": rank,
                    "exact_match": query.lower() in fact.lower(),
                    "matched_terms": query.split(),
                    "match_reasons": ["graph_neighbors"],
                    "freshness": 1.0,
                    "usage_signal": 0.5,
                    "path": [str(record.get("source_name")), str(record.get("relation")), str(record.get("target_name"))],
                    "payload": {
                        "uuid": str(record.get("uuid") or f"graph:{rank}"),
                        "layer": MemoryLayer.SEMANTIC.value,
                        "name": fact[:80] or "Graph fact",
                        "content": fact,
                        "metadata": {
                            "source_id": record.get("source_id"),
                            "target_id": record.get("target_id"),
                            "relation": record.get("relation"),
                        },
                        "source": "graph",
                        "indexed_text": fact,
                    },
                }
            )
        return results

    def get_outbox_health(self) -> Dict[str, Dict[str, Any]]:
        """Expose semantic outbox health for system stats."""
        return self.store.get_outbox_health()

    def replay_due_outbox(
        self,
        *,
        target_backend: Optional[str] = None,
        limit_per_backend: int = 100,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Replay due outbox rows immediately."""
        requested_backends = [target_backend] if target_backend else (self.store.list_outbox_backends() or list(_DEFAULT_OUTBOX_BACKENDS))
        summary: Dict[str, Dict[str, int]] = {}
        total_affected = 0

        for backend in requested_backends:
            due_count = self.store.count_outbox_rows(
                target_backend=backend,
                statuses=("pending", "retry_wait", "failed"),
                due_only=True,
            )
            attempted = 0
            if not dry_run:
                remaining = max(0, int(limit_per_backend))
                while remaining > 0:
                    processed = self._drain_outbox_backend(backend, limit=min(20, remaining))
                    if processed == 0:
                        break
                    attempted += processed
                    remaining -= processed
            summary[backend] = {
                "due_count": due_count,
                "attempted_count": attempted,
            }
            total_affected += due_count if dry_run else attempted

        return {
            "affected": total_affected,
            "dry_run": dry_run,
            "backends": summary,
        }

    def rebuild_graph_projection(
        self,
        *,
        dry_run: bool = False,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Re-enqueue graph projection tasks from SQLite semantic truth."""
        nodes = self.store.fetch_graph_rebuild_nodes(limit=limit)
        remaining = None if limit is None else max(0, limit - len(nodes))
        edges = self.store.fetch_graph_rebuild_edges(limit=remaining)

        if dry_run:
            return {
                "available": self._graphiti is not None,
                "affected": len(nodes) + len(edges),
                "nodes": len(nodes),
                "edges": len(edges),
                "dry_run": True,
            }

        if self._graphiti is None and not _REQUIRE_GRAPHITI:
            return {
                "available": False,
                "affected": 0,
                "nodes": len(nodes),
                "edges": len(edges),
                "dry_run": False,
                "message": "Graphiti client not initialized",
            }

        for row in nodes:
            payload = {
                "id": row["id"],
                "op_type": "add_entity",
                "name": row["name"],
                "graph_name": f"entity_{row['name']}",
                "episode_body": f"{row['name']}: {row['summary'] or ''}",
                "source_description": f"Entity type: {row['entity_type']}",
                "created_at": row["created_at"],
                "group_id": _sanitize_graph_group_id(row["group_id"]),
            }
            self.store.enqueue_outbox(
                operation_id=str(uuid4()),
                target_backend="graph",
                record_id=str(row["id"]),
                op_type="add_entity",
                payload=payload,
                dedupe_key=f"add_entity:{row['id']}:graph",
                projector_version=self._runtime_config.projector_version,
            )

        for row in edges:
            fact_text = row["fact_text"] or f"{row['source_id']} {row['relation_type']} {row['target_id']}"
            payload = {
                "id": row["id"],
                "op_type": "add_fact",
                "graph_name": f"fact_{row['id']}",
                "episode_body": f"{fact_text} | {row['metadata_json'] or '{}'}",
                "source_description": f"Fact: {row['relation_type']}",
                "valid_at": row["valid_at"],
            }
            self.store.enqueue_outbox(
                operation_id=str(uuid4()),
                target_backend="graph",
                record_id=str(row["id"]),
                op_type="add_fact",
                payload=payload,
                dedupe_key=f"add_fact:{row['id']}:graph",
                projector_version=self._runtime_config.projector_version,
            )

        self._submit_outbox_worker("graph")
        return {
            "available": True,
            "affected": len(nodes) + len(edges),
            "nodes": len(nodes),
            "edges": len(edges),
            "dry_run": False,
        }

    async def add_entity(
        self,
        name: str,
        entity_type: EntityType,
        summary: Optional[str] = None,
        memory_layer: MemoryLayer = MemoryLayer.SEMANTIC,
        confidence: float = 0.7,
        source_episode: Optional[str] = None,
        preprocess: bool = True,
        group_id: Optional[str] = None,
    ) -> SynapseNode:
        """
        Add an entity to semantic memory.

        Args:
            name: Entity name
            entity_type: Type of entity
            summary: Evolving summary of the entity
            memory_layer: Which memory layer (default: SEMANTIC)
            confidence: Confidence score (0.0 to 1.0)
            source_episode: Source episode ID
            preprocess: Apply Thai NLP preprocessing

        Returns:
            Created SynapseNode
        """
        now = utcnow()

        # Preprocess name and summary for Thai
        processed_name = name
        processed_summary = summary
        if preprocess:
            preprocessor = _get_nlp_preprocessor()
            if preprocessor:
                # Preserve user-provided names/aliases exactly; Thai spellcheck can
                # incorrectly rewrite proper nouns such as personal nicknames.
                result = preprocessor.preprocess_for_extraction(name, spellcheck=False)
                processed_name = result.processed

                if summary:
                    summary_result = preprocessor.preprocess_for_extraction(
                        summary,
                        spellcheck=False,
                    )
                    processed_summary = summary_result.processed

        node_id = str(uuid4())

        node = SynapseNode(
            id=node_id,
            type=entity_type,
            name=processed_name,
            summary=processed_summary,
            memory_layer=memory_layer,
            confidence=confidence,
            decay_score=1.0,  # Fresh node
            access_count=0,
            created_at=now,
            updated_at=now,
            source_episode=source_episode,
            chat_id=_sanitize_graph_group_id(group_id),
        )

        self.store.save_node(node)

        vector_payload = {
            "id": node.id,
            "entity_type": entity_type.value if hasattr(entity_type, "value") else str(entity_type),
            "name": node.name,
            "summary": node.summary,
            "memory_layer": node.memory_layer.value if hasattr(node.memory_layer, "value") else str(node.memory_layer),
            "confidence": node.confidence,
            "decay_score": node.decay_score,
            "access_count": node.access_count,
            "created_at": node.created_at.isoformat(),
            "updated_at": node.updated_at.isoformat(),
            "source_episode": node.source_episode,
            "created_by": node.created_by,
        }
        if getattr(self.vector_client, "enabled", True):
            self._queue_outbox("vector", node.id, "add_entity", vector_payload)

        if self._graphiti is not None or _REQUIRE_GRAPHITI:
            graph_payload = {
                "id": node.id,
                "op_type": "add_entity",
                "name": node.name,
                "graph_name": f"entity_{processed_name}",
                "episode_body": f"{processed_name}: {processed_summary or ''}",
                "source_description": f"Entity type: {entity_type.value}",
                "created_at": now.isoformat(),
                "group_id": node.chat_id,
            }
            self._queue_outbox("graph", node.id, "add_entity", graph_payload)

        return node

    async def add_fact(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        confidence: float = 0.7,
        valid_at: Optional[datetime] = None,
        source_episode: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        group_id: Optional[str] = None,
    ) -> SynapseEdge:
        """
        Add a fact (relationship) to semantic memory.

        Args:
            source_id: Source node ID
            target_id: Target node ID
            relation_type: Type of relationship
            confidence: Confidence score
            valid_at: When this became true (default: now)
            source_episode: Source episode ID
            metadata: Additional metadata

        Returns:
            Created SynapseEdge
        """
        now = utcnow()
        edge_id = f"edge_{source_id}_{relation_type}_{target_id}"

        edge = SynapseEdge(
            id=edge_id,
            source_id=source_id,
            target_id=target_id,
            type=relation_type,
            valid_at=valid_at or now,
            invalid_at=None,
            confidence=confidence,
            source_episode=source_episode,
            metadata=metadata or {},
        )

        fact_text = f"{source_id} {relation_type.value} {target_id}"
        self.store.save_edge(edge, fact_text=fact_text)
        if self._graphiti is not None or _REQUIRE_GRAPHITI:
            graph_payload = {
                "id": edge.id,
                "op_type": "add_fact",
                "graph_name": f"fact_{edge_id}",
                "episode_body": f"{fact_text} | {metadata or {}}",
                "source_description": f"Fact: {relation_type.value}",
                "valid_at": (valid_at or now).isoformat(),
                "group_id": _sanitize_graph_group_id(group_id),
            }
            self._queue_outbox("graph", edge.id, "add_fact", graph_payload)

        return edge

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.1,
        entity_types: Optional[List[EntityType]] = None,
        use_hybrid: bool = True,
        preprocess_query: bool = True,
    ) -> List[SearchResult]:
        """
        Search semantic memory.

        Args:
            query: Search query
            limit: Maximum results
            min_score: Minimum decay score threshold
            entity_types: Filter by entity types
            use_hybrid: Use hybrid search (vector + FTS + graph)
            preprocess_query: Apply Thai NLP preprocessing

        Returns:
            List of SearchResult
        """
        now = utcnow()
        candidates = self.fetch_vector_candidates(query=query, limit=max(limit * 2, limit))
        if use_hybrid:
            lexical = self.fetch_lexical_candidates(query=query, limit=max(limit * 2, limit))
            by_id = {candidate["record_id"]: candidate for candidate in candidates}
            for item in lexical:
                existing = by_id.get(item["record_id"])
                if existing is None:
                    by_id[item["record_id"]] = item
                else:
                    existing["backend_score"] = max(existing["backend_score"], item["backend_score"])
            candidates = list(by_id.values())

        results = []
        for candidate in candidates[:limit]:
            node = self.store.get_node(candidate["record_id"])
            if node is None:
                continue
            if entity_types and node.type not in entity_types:
                continue
            decay_score = self.compute_decay_score(node, now)
            combined_score = max(0.0, min(1.0, (float(candidate["backend_score"]) + decay_score) / 2.0))
            if combined_score < min_score:
                continue
            results.append(
                SearchResult(
                    node=node,
                    score=combined_score,
                    source=str(candidate["backend"]),
                    path=candidate.get("path"),
                )
            )
        return results[:limit]

    async def get_entity(self, entity_id: str) -> Optional[SynapseNode]:
        """
        Get entity by ID.

        Increments access count and updates decay score.

        Args:
            entity_id: Entity identifier

        Returns:
            SynapseNode or None
        """
        await self._ensure_graphiti()

        node = self.store.get_node(entity_id)
        if node is not None:
            return node

        try:
            matches = self.vector_client.search(
                collection_name=self.collection_name,
                query_text=entity_id,
                limit=1,
            )
            if matches:
                node = self._payload_to_node(matches[0]["payload"])
                if node and node.id == entity_id:
                    return node
        except Exception as exc:
            self._warn_vector_issue(exc)

        # Try to get from Graphiti if available
        graphiti_client = self._bound_graphiti_client()
        if graphiti_client is not None:
            try:
                # Search for the entity in Graphiti
                results = await graphiti_client.search(
                    query=entity_id,
                    num_results=1,
                )
                if results:
                    # Convert Graphiti result to SynapseNode
                    edge = results[0]
                    # Extract entity name from the fact
                    fact_text = getattr(edge, 'fact', '') or str(edge)
                    # Create a SynapseNode from the result
                    return SynapseNode(
                        id=entity_id,
                        type=EntityType.CONCEPT,
                        name=entity_id,
                        summary=fact_text,
                        memory_layer=MemoryLayer.SEMANTIC,
                        confidence=0.7,
                        decay_score=1.0,
                        access_count=1,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
            except Exception as e:
                logger.warning(f"Failed to get entity from Graphiti: {e}")

        return None

    async def supersede_fact(
        self,
        old_edge_id: str,
        new_edge: SynapseEdge,
    ) -> SynapseEdge:
        """
        Mark old fact as superseded by new fact.

        Sets invalid_at on old edge and creates new edge.

        Args:
            old_edge_id: ID of edge to supersede
            new_edge: New edge to create

        Returns:
            Created new SynapseEdge
        """
        now = utcnow()

        # Mark old edge as invalid by adding a superseding fact
        if self._graphiti is not None or _REQUIRE_GRAPHITI:
            self._queue_outbox(
                "graph",
                old_edge_id,
                "invalidate_fact",
                {
                    "id": old_edge_id,
                    "op_type": "invalidate_fact",
                    "graph_name": f"invalidate_{old_edge_id}",
                    "episode_body": f"Fact {old_edge_id} is no longer valid as of {now.isoformat()}",
                    "source_description": "Fact invalidation",
                    "created_at": now.isoformat(),
                },
            )

        # Create new edge
        new_edge.valid_at = now
        new_edge.metadata["supersedes"] = old_edge_id
        self.store.save_edge(
            new_edge,
            fact_text=(
                f"{new_edge.source_id} "
                f"{new_edge.type.value if hasattr(new_edge.type, 'value') else new_edge.type} "
                f"{new_edge.target_id}"
            ),
        )
        if self._graphiti is not None or _REQUIRE_GRAPHITI:
            self._queue_outbox(
                "graph",
                new_edge.id,
                "graph_event",
                {
                    "id": new_edge.id,
                    "op_type": "graph_event",
                    "graph_name": f"fact_{new_edge.id}",
                    "episode_body": (
                        f"{new_edge.source_id} "
                        f"{new_edge.type.value if hasattr(new_edge.type, 'value') else new_edge.type} "
                        f"{new_edge.target_id}"
                    ),
                    "source_description": (
                        "Superseding fact: "
                        f"{new_edge.type.value if hasattr(new_edge.type, 'value') else new_edge.type}"
                    ),
                    "created_at": now.isoformat(),
                },
            )

        return new_edge

    async def update_entity(
        self,
        entity_id: str,
        summary: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Optional[SynapseNode]:
        """
        Update entity properties.

        Args:
            entity_id: Entity identifier
            summary: New summary (appended to existing)
            confidence: New confidence score

        Returns:
            Updated SynapseNode or None
        """
        # Get existing entity from Qdrant
        node = await self.get_entity(entity_id)
        if node is None:
            return None

        # Update properties
        if summary is not None:
            if node.summary:
                node.summary = f"{node.summary}\n{summary}"
            else:
                node.summary = summary

        if confidence is not None:
            node.confidence = max(0.0, min(1.0, confidence))

        node.updated_at = utcnow()
        node.access_count += 1

        self.store.save_node(node)

        # Update in Qdrant
        self._index_entity(node)

        # Persist update to Graphiti
        if self._graphiti is not None or _REQUIRE_GRAPHITI:
            self._queue_outbox(
                "graph",
                entity_id,
                "update_entity",
                {
                    "id": entity_id,
                    "op_type": "update_entity",
                    "graph_name": f"update_{entity_id}",
                    "episode_body": f"Updated {node.name}: {summary or ''}",
                    "source_description": (
                        "Entity update: "
                        f"{node.type.value if hasattr(node.type, 'value') else node.type}"
                    ),
                    "created_at": node.updated_at.isoformat(),
                    "group_id": node.chat_id,
                },
            )

        return node

    def compute_decay_score(
        self,
        node: SynapseNode,
        now: Optional[datetime] = None,
    ) -> float:
        """
        Compute decay score for a node.

        Args:
            node: SynapseNode to compute score for
            now: Current time

        Returns:
            Decay score (0.0 to 1.0)
        """
        return compute_decay_score(
            updated_at=node.updated_at,
            access_count=node.access_count,
            memory_layer=node.memory_layer,
            now=now,
        )

    async def should_forget_node(
        self,
        node: SynapseNode,
        now: Optional[datetime] = None,
    ) -> bool:
        """
        Check if node should be forgotten.

        Args:
            node: SynapseNode to check
            now: Current time

        Returns:
            True if should forget
        """
        decay_score = self.compute_decay_score(node, now)
        return should_forget(decay_score, node.expires_at, now)

    async def get_related_entities(
        self,
        entity_id: str,
        relation_types: Optional[List[RelationType]] = None,
        max_depth: int = 2,
        limit: int = 20,
    ) -> List[SynapseNode]:
        """
        Get entities related to a given entity.

        Args:
            entity_id: Starting entity ID
            relation_types: Filter by relation types
            max_depth: Maximum traversal depth
            limit: Maximum results

        Returns:
            List of related SynapseNodes
        """
        await self._ensure_graphiti()

        related: List[SynapseNode] = []

        # Use Graphiti search for graph traversal
        graphiti_client = self._bound_graphiti_client()
        if graphiti_client is not None:
            try:
                # Build query for related entities
                query = f"related to {entity_id}"
                if relation_types:
                    query += " " + " ".join(rt.value for rt in relation_types)

                results = await graphiti_client.search(
                    query=query,
                    num_results=limit * max_depth,
                )

                for edge in results:
                    # Extract related entity from the fact
                    fact_text = getattr(edge, 'fact', '') or str(edge)
                    source_uuid = getattr(edge, 'source_node_uuid', None)
                    target_uuid = getattr(edge, 'target_node_uuid', None)

                    # Determine the related entity ID
                    related_id = target_uuid if source_uuid == entity_id else source_uuid
                    if related_id is None:
                        continue

                    # Skip if already in results
                    if related_id in [n.id for n in related]:
                        continue

                    # Create a SynapseNode for the related entity
                    node = SynapseNode(
                        id=related_id,
                        type=EntityType.CONCEPT,
                        name=related_id,
                        summary=fact_text,
                        memory_layer=MemoryLayer.SEMANTIC,
                        confidence=0.7,
                        decay_score=1.0,
                        access_count=1,
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    related.append(node)

                    if len(related) >= limit:
                        break

            except Exception as e:
                logger.warning(f"Graph traversal failed: {e}")

        return related

    async def cleanup_forgotten(self, batch_size: int = 100) -> int:
        """
        Remove forgotten nodes from storage.

        Args:
            batch_size: Number of nodes to process per batch

        Returns:
            Number of nodes removed
        """
        await self._ensure_graphiti()

        count = 0
        now = utcnow()

        # Scan Qdrant for forgotten nodes
        try:
            # Get all nodes (this is a simplified approach)
            # In production, you'd use scroll/iterator
            all_matches = self.vector_client.search(
                collection_name=self.collection_name,
                query_text="",  # Empty query to get all
                limit=batch_size * 10,
            )

            for match in all_matches:
                node = self._payload_to_node(match["payload"])
                if node is None:
                    continue

                # Check if node should be forgotten
                if await self.should_forget_node(node, now):
                    # Delete from Qdrant
                    try:
                        self.vector_client.delete(
                            collection_name=self.collection_name,
                            ids=[node.id],
                        )
                        count += 1
                        logger.debug(f"Forgotten node '{node.id}' removed from Qdrant")
                    except Exception as e:
                        logger.warning(f"Failed to delete node '{node.id}': {e}")

                    if count >= batch_size:
                        break

        except Exception as exc:
            self._warn_vector_issue(exc)

        return count


# Singleton instance
_manager: Optional[SemanticManager] = None


def get_manager(graphiti_client=None) -> SemanticManager:
    """Get singleton SemanticManager instance."""
    global _manager
    if _manager is None:
        _manager = SemanticManager(graphiti_client)
    return _manager


# Async convenience functions
async def search(query: str, limit: int = 10) -> List[SearchResult]:
    """Search semantic memory."""
    return await get_manager().search(query, limit)


async def add_entity(name: str, entity_type: EntityType, **kwargs) -> SynapseNode:
    """Add entity to semantic memory."""
    return await get_manager().add_entity(name, entity_type, **kwargs)


async def add_fact(source_id: str, target_id: str, relation_type: RelationType, **kwargs) -> SynapseEdge:
    """Add fact to semantic memory."""
    return await get_manager().add_fact(source_id, target_id, relation_type, **kwargs)
