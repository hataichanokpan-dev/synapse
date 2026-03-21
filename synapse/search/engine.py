"""Hybrid retrieval engine for Synapse."""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional

from synapse.layers import MemoryLayer
from synapse.nlp.preprocess import get_preprocessor

from .cache import LayerGenerationTracker, TTLCache
from .config import SearchWeights
from .intent import QueryIntentAnalyzer
from .telemetry import HybridSearchTelemetry
from .types import HybridCandidate, HybridSearchError, HybridSearchPlan, QueryType, SearchMode

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class HybridSearchEngine:
    """Runtime that executes hybrid search against Synapse layers."""

    def __init__(
        self,
        layer_manager,
        graphiti_client=None,
        *,
        weights: Optional[SearchWeights] = None,
        telemetry: Optional[HybridSearchTelemetry] = None,
        generations: Optional[LayerGenerationTracker] = None,
    ):
        self.layers = layer_manager
        self.graphiti = graphiti_client
        self.weights = weights or SearchWeights()
        self.telemetry = telemetry or HybridSearchTelemetry()
        self.generations = generations or LayerGenerationTracker()
        self.intent_analyzer = QueryIntentAnalyzer()
        self.query_cache = TTLCache(ttl_seconds=10.0, maxsize=256)
        self.embedding_cache = TTLCache(ttl_seconds=600.0, maxsize=1024)
        self.graph_cache = TTLCache(ttl_seconds=30.0, maxsize=512)
        self._lexical_semaphore = asyncio.Semaphore(_env_int("SYNAPSE_HYBRID_LEXICAL_CONCURRENCY", 64))
        self._vector_semaphore = asyncio.Semaphore(_env_int("SYNAPSE_HYBRID_VECTOR_CONCURRENCY", 16))
        self._graph_semaphore = asyncio.Semaphore(_env_int("SYNAPSE_HYBRID_GRAPH_CONCURRENCY", 8))

    def bump_generations(self, *keys: str) -> None:
        self.generations.bump(*keys)
        self.query_cache.clear()

    async def search(
        self,
        *,
        query: str,
        layers: Optional[List[MemoryLayer]] = None,
        limit: int = 10,
        mode: str | SearchMode = SearchMode.HYBRID_AUTO,
        query_type: str | QueryType = QueryType.AUTO,
        explain: bool = False,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        plan = self._build_plan(
            query=query,
            layers=layers,
            limit=limit,
            mode=mode,
            query_type=query_type,
            explain=explain,
            user_id=user_id,
            group_id=group_id,
        )
        deadline = start + (plan.total_timeout_ms / 1000.0)

        cache_key = self._cache_key(plan)
        if plan.mode == SearchMode.HYBRID_AUTO and not plan.explain:
            cached = self.query_cache.get(cache_key)
            if cached is not None:
                cached_response = copy.deepcopy(cached)
                telemetry = dict(cached_response.get("telemetry", {}))
                telemetry["cache_hit_query"] = True
                self.telemetry.record_query(telemetry)
                return cached_response

        pinned_context = self._fetch_working_context(query) if MemoryLayer.WORKING in plan.layers else []
        structured_candidates = []
        if self._should_fetch_user_model(plan):
            structured_candidates = self._fetch_user_model(query, user_id=plan.user_id, limit=plan.limit)

        backend_latency: Dict[str, float] = {
            "lexical": 0.0,
            "vector": 0.0,
            "graph": 0.0,
            "structured": 0.0,
            "rerank": 0.0,
        }
        used_backends = set()
        degraded_backends: List[str] = []
        warnings: List[str] = []
        timeouts: List[str] = []
        cache_hit_embedding = False
        cache_hit_graph = False

        remaining_budget = lambda: deadline - time.perf_counter()
        tasks = self._build_fetch_tasks(plan, remaining_budget)
        running_tasks = {name: asyncio.create_task(task) for name, task in tasks.items()}
        fetch_results: Dict[str, Dict[str, Any]] = {}
        for name, task in running_tasks.items():
            fetch_results[name] = await task
            fetch_meta = fetch_results[name]
            kind = fetch_meta.get("kind", "lexical")
            backend_latency[kind] += float(fetch_meta.get("latency_ms", 0.0))
            if fetch_meta.get("timeout"):
                degraded_backends.append(name)
                timeouts.append(name)
            if fetch_meta.get("warning"):
                degraded_backends.append(name)
                warnings.append(str(fetch_meta["warning"]))
            if fetch_meta.get("cache_hit_embedding"):
                cache_hit_embedding = True

        if MemoryLayer.SEMANTIC in plan.layers:
            semantic_seed_candidates = (
                fetch_results.get("semantic_lexical", {}).get("items", [])[:8]
                + fetch_results.get("semantic_vector", {}).get("items", [])[:8]
            )
            graph_result = await self._run_graph_fetch(plan, semantic_seed_candidates, remaining_budget)
            fetch_results["semantic_graph"] = graph_result
            backend_latency["graph"] += float(graph_result.get("latency_ms", 0.0))
            if graph_result.get("timeout"):
                degraded_backends.append("semantic_graph")
                timeouts.append("semantic_graph")
            if graph_result.get("warning"):
                degraded_backends.append("semantic_graph")
                warnings.append(str(graph_result["warning"]))
            if graph_result.get("cache_hit_graph"):
                cache_hit_graph = True

        if plan.mode == SearchMode.HYBRID_STRICT:
            missing_backends = self._strict_backend_failures(plan, fetch_results)
            if missing_backends:
                telemetry_event = {
                    "mode": plan.mode.value,
                    "query_type_detected": plan.query_type.value,
                    "latency_ms_total": round((time.perf_counter() - start) * 1000, 3),
                    "used_backends": sorted(used_backends),
                    "timeouts": list(timeouts),
                    "degraded": True,
                    "strict_failure": True,
                    "cache_hit_query": False,
                    "cache_hit_embedding": cache_hit_embedding,
                    "cache_hit_graph": cache_hit_graph,
                }
                self.telemetry.record_query(telemetry_event)
                raise HybridSearchError(
                    "Required hybrid backends unavailable",
                    degraded_backends=sorted(set(degraded_backends + missing_backends)),
                )

        candidate_map = self._collect_candidates(fetch_results, structured_candidates)
        candidates = list(candidate_map.values())
        for candidate in candidates:
            used_backends.update(candidate.sources)

        self._apply_rrf(plan, candidates)
        rerank_started = time.perf_counter()
        ranked = self._rerank(plan, candidates)
        backend_latency["rerank"] = round((time.perf_counter() - rerank_started) * 1000, 3)

        results = [self._candidate_to_result(plan, item, degraded_backends) for item in ranked[: plan.limit]]
        grouped_layers = self._group_results(results)

        telemetry_event = {
            "query_id": f"{int(start * 1000)}-{abs(hash(plan.normalized_query)) % 10000}",
            "mode": plan.mode.value,
            "query_type_detected": plan.query_type.value,
            "layers": [layer.value for layer in plan.layers],
            "used_backends": sorted(used_backends),
            "latency_ms_total": round((time.perf_counter() - start) * 1000, 3),
            "latency_ms_lexical": round(backend_latency["lexical"], 3),
            "latency_ms_vector": round(backend_latency["vector"], 3),
            "latency_ms_graph": round(backend_latency["graph"], 3),
            "latency_ms_structured": round(backend_latency["structured"], 3),
            "latency_ms_rerank": round(backend_latency["rerank"], 3),
            "cache_hit_query": False,
            "cache_hit_embedding": cache_hit_embedding,
            "cache_hit_graph": cache_hit_graph,
            "degraded": bool(degraded_backends),
            "strict_failure": False,
            "timeouts": list(timeouts),
            "top_result_ids": [result["uuid"] for result in results[:5]],
        }
        self.telemetry.record_query(telemetry_event)

        response = {
            "query": query,
            "results": results,
            "ranked_results": results,
            "layers": grouped_layers,
            "graphiti": [],
            "mode_used": plan.mode.value,
            "query_type_detected": plan.query_type.value,
            "used_backends": sorted(used_backends),
            "degraded": bool(degraded_backends),
            "warnings": sorted(set(warnings)),
            "pinned_context": pinned_context,
            "degraded_backends": sorted(set(degraded_backends)),
            "telemetry": telemetry_event,
        }

        if plan.mode == SearchMode.HYBRID_AUTO and not plan.explain:
            self.query_cache.set(cache_key, copy.deepcopy(response))
        return response

    def snapshot_metrics(self) -> Dict[str, Any]:
        return self.telemetry.snapshot()

    def _build_plan(
        self,
        *,
        query: str,
        layers: Optional[List[MemoryLayer]],
        limit: int,
        mode: str | SearchMode,
        query_type: str | QueryType,
        explain: bool,
        user_id: Optional[str],
        group_id: Optional[str],
    ) -> HybridSearchPlan:
        normalized_query = self._normalize_query(query)
        selected_layers = list(layers or [
            MemoryLayer.USER_MODEL,
            MemoryLayer.PROCEDURAL,
            MemoryLayer.SEMANTIC,
            MemoryLayer.EPISODIC,
            MemoryLayer.WORKING,
        ])
        mode_enum = mode if isinstance(mode, SearchMode) else SearchMode(str(mode))
        requested_query_type = query_type.value if isinstance(query_type, QueryType) else str(query_type)
        detected_query_type = self.intent_analyzer.analyze(
            query,
            requested_query_type,
            [layer.value for layer in selected_layers],
        )
        return HybridSearchPlan(
            query=query,
            normalized_query=normalized_query,
            query_type=detected_query_type,
            mode=mode_enum,
            limit=limit,
            layers=selected_layers,
            explain=explain,
            user_id=user_id,
            group_id=group_id,
            lexical_budget=max(limit * 3, 20),
            vector_budget=max(limit * 3, 20),
            graph_budget=max(limit * 2, 15),
            total_timeout_ms=_env_int("SYNAPSE_HYBRID_TIMEOUT_MS", 800),
            timeout_ms_by_backend={
                "lexical": _env_int("SYNAPSE_HYBRID_LEXICAL_TIMEOUT_MS", 250),
                "vector": _env_int("SYNAPSE_HYBRID_VECTOR_TIMEOUT_MS", 400),
                "graph": _env_int("SYNAPSE_HYBRID_GRAPH_TIMEOUT_MS", 500),
                "structured": _env_int("SYNAPSE_HYBRID_STRUCTURED_TIMEOUT_MS", 120),
                "rerank": _env_int("SYNAPSE_HYBRID_RERANK_TIMEOUT_MS", 120),
            },
            rerank_top_k=self.weights.rerank_top_k,
            weights=self.weights.get(detected_query_type.value),
        )

    def _cache_key(self, plan: HybridSearchPlan) -> tuple[Any, ...]:
        layer_keys = tuple(sorted(layer.value for layer in plan.layers))
        generation = self.generations.snapshot(*layer_keys, "semantic_graph", "semantic_lexical")
        return (
            plan.normalized_query,
            plan.query_type.value,
            plan.mode.value,
            layer_keys,
            plan.user_id or "",
            plan.group_id or "",
            self.weights.version,
            generation,
        )

    def _normalize_query(self, query: str) -> str:
        processed = get_preprocessor().tokenize_for_fts(query or "")
        processed = re.sub(r"\s+", " ", processed).strip()
        return processed or (query or "").strip()

    def _build_fetch_tasks(self, plan: HybridSearchPlan, remaining_budget) -> Dict[str, Any]:
        tasks: Dict[str, Any] = {}
        if MemoryLayer.PROCEDURAL in plan.layers:
            tasks["procedural_lexical"] = self._run_sync_fetch(
                "lexical",
                self.layers.procedural.fetch_lexical_candidates,
                query=plan.query,
                limit=plan.lexical_budget,
                timeout_ms=plan.timeout_ms_by_backend["lexical"],
                budget_s=remaining_budget,
            )
            tasks["procedural_vector"] = self._run_sync_fetch(
                "vector",
                self.layers.procedural.fetch_vector_candidates,
                query=plan.query,
                limit=plan.vector_budget,
                timeout_ms=plan.timeout_ms_by_backend["vector"],
                budget_s=remaining_budget,
                embedding_cache=self.embedding_cache,
            )

        if MemoryLayer.EPISODIC in plan.layers:
            tasks["episodic_lexical"] = self._run_sync_fetch(
                "lexical",
                self.layers.episodic.fetch_lexical_candidates,
                query=plan.query,
                limit=plan.lexical_budget,
                timeout_ms=plan.timeout_ms_by_backend["lexical"],
                budget_s=remaining_budget,
                user_id=plan.user_id,
            )
            tasks["episodic_vector"] = self._run_sync_fetch(
                "vector",
                self.layers.episodic.fetch_vector_candidates,
                query=plan.query,
                limit=plan.vector_budget,
                timeout_ms=plan.timeout_ms_by_backend["vector"],
                budget_s=remaining_budget,
                user_id=plan.user_id,
                embedding_cache=self.embedding_cache,
            )

        if MemoryLayer.SEMANTIC in plan.layers:
            tasks["semantic_lexical"] = self._run_sync_fetch(
                "lexical",
                self.layers.semantic.fetch_lexical_candidates,
                query=plan.query,
                limit=plan.lexical_budget,
                timeout_ms=plan.timeout_ms_by_backend["lexical"],
                budget_s=remaining_budget,
            )
            tasks["semantic_vector"] = self._run_sync_fetch(
                "vector",
                self.layers.semantic.fetch_vector_candidates,
                query=plan.query,
                limit=plan.vector_budget,
                timeout_ms=plan.timeout_ms_by_backend["vector"],
                budget_s=remaining_budget,
                embedding_cache=self.embedding_cache,
            )
        return tasks

    def _should_fetch_user_model(self, plan: HybridSearchPlan) -> bool:
        if MemoryLayer.USER_MODEL not in plan.layers:
            return False
        return plan.query_type == QueryType.PREFERENCE or plan.layers == [MemoryLayer.USER_MODEL]

    def _fetch_working_context(self, query: str) -> List[Dict[str, Any]]:
        matches = []
        for item in self.layers._search_working_memory(query, limit=5):
            matches.append({
                "key": item.get("key"),
                "value": item.get("value"),
                "match_type": item.get("match_type"),
                "relevance": item.get("relevance", 1.0),
            })
        return matches

    def _fetch_user_model(self, query: str, *, user_id: Optional[str], limit: int) -> List[Dict[str, Any]]:
        results = self.layers._search_user_model(query, user_id=user_id, limit=limit)
        items = []
        for index, item in enumerate(results, start=1):
            preview = item.get("note") or item.get("topic") or item.get("area") or "User preference"
            items.append({
                "record_id": f"user:{user_id or 'default'}:{index}",
                "layer": MemoryLayer.USER_MODEL,
                "backend": "structured",
                "backend_score": float(item.get("relevance", 1.0)),
                "rank": index,
                "exact_match": query.lower() in str(preview).lower(),
                "matched_terms": [query],
                "match_reasons": [str(item.get("type", "preference"))],
                "freshness": 1.0,
                "usage_signal": 1.0,
                "payload": {
                    "uuid": f"user:{user_id or 'default'}:{index}",
                    "layer": MemoryLayer.USER_MODEL.value,
                    "name": item.get("type", "preference"),
                    "content": preview,
                    "metadata": item,
                    "source": "user_model",
                },
            })
        return items

    async def _run_sync_fetch(self, kind: str, fn, *, timeout_ms: int, budget_s, **kwargs) -> Dict[str, Any]:
        semaphore = self._lexical_semaphore if kind == "lexical" else self._vector_semaphore
        started = time.perf_counter()
        remaining_s = budget_s()
        if remaining_s <= 0:
            return {"items": [], "timeout": True, "latency_ms": 0.0, "warning": f"{kind} deadline exhausted", "kind": kind}
        timeout_s = min(timeout_ms / 1000.0, remaining_s)
        try:
            async with semaphore:
                result = await asyncio.wait_for(asyncio.to_thread(fn, **kwargs), timeout=timeout_s)
            return {
                "items": result or [],
                "timeout": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "kind": kind,
            }
        except asyncio.TimeoutError:
            return {
                "items": [],
                "timeout": True,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "warning": f"{kind} fetch timed out",
                "kind": kind,
            }
        except Exception as exc:
            logger.debug("Hybrid %s fetch failed: %s", kind, exc)
            return {
                "items": [],
                "timeout": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "warning": f"{kind} fetch failed: {exc}",
                "kind": kind,
            }

    async def _run_graph_fetch(self, plan: HybridSearchPlan, seed_candidates: List[Dict[str, Any]], budget_s) -> Dict[str, Any]:
        started = time.perf_counter()
        remaining_s = budget_s()
        if remaining_s <= 0:
            return {"items": [], "timeout": True, "latency_ms": 0.0, "warning": "graph deadline exhausted", "kind": "graph"}
        timeout_s = min(plan.timeout_ms_by_backend["graph"] / 1000.0, remaining_s)

        cache_key = (
            plan.normalized_query,
            tuple(sorted(str(item.get("record_id")) for item in seed_candidates[:8] if item.get("record_id"))),
            plan.graph_budget,
        )
        cached = self.graph_cache.get(cache_key)
        if cached is not None:
            return {"items": cached, "timeout": False, "latency_ms": 0.0, "cache_hit_graph": True, "kind": "graph"}

        if not hasattr(self.layers.semantic, "fetch_graph_candidates"):
            return {"items": [], "timeout": False, "latency_ms": 0.0, "warning": "graph fetch unavailable", "kind": "graph"}
        if getattr(self.layers.semantic, "_graphiti", None) is None:
            return {"items": [], "timeout": False, "latency_ms": 0.0, "warning": "graph backend unavailable", "kind": "graph"}

        seed_ids = [str(item.get("record_id")) for item in seed_candidates[:8] if item.get("record_id")]
        try:
            async with self._graph_semaphore:
                items = await asyncio.wait_for(
                    self.layers.semantic.fetch_graph_candidates(
                        plan.query,
                        plan.graph_budget,
                        seed_ids=seed_ids,
                        query_type=plan.query_type.value,
                    ),
                    timeout=timeout_s,
                )
            self.graph_cache.set(cache_key, items or [])
            return {"items": items or [], "timeout": False, "latency_ms": round((time.perf_counter() - started) * 1000, 3), "kind": "graph"}
        except asyncio.TimeoutError:
            return {"items": [], "timeout": True, "latency_ms": round((time.perf_counter() - started) * 1000, 3), "warning": "graph fetch timed out", "kind": "graph"}
        except Exception as exc:
            logger.debug("Hybrid graph fetch failed: %s", exc)
            return {"items": [], "timeout": False, "latency_ms": round((time.perf_counter() - started) * 1000, 3), "warning": f"graph fetch failed: {exc}", "kind": "graph"}

    def _strict_backend_failures(self, plan: HybridSearchPlan, fetch_results: Dict[str, Dict[str, Any]]) -> List[str]:
        missing = []
        require_vector = os.getenv("SYNAPSE_HYBRID_REQUIRE_VECTOR", "false").strip().lower() in {"1", "true", "yes", "on"} or plan.mode == SearchMode.HYBRID_STRICT
        require_graph = os.getenv("SYNAPSE_HYBRID_REQUIRE_GRAPH", "false").strip().lower() in {"1", "true", "yes", "on"}
        if plan.query_type in {QueryType.RELATIONAL, QueryType.SEMANTIC, QueryType.MIXED} and MemoryLayer.SEMANTIC in plan.layers:
            require_graph = True
        outbox_health = {}
        if hasattr(self.layers, "semantic") and hasattr(self.layers.semantic, "get_outbox_health"):
            try:
                outbox_health = self.layers.semantic.get_outbox_health() or {}
            except Exception:
                outbox_health = {}

        if require_vector:
            vector_keys = [key for key in fetch_results if key.endswith("_vector")]
            if not vector_keys or any(fetch_results[key].get("warning") or fetch_results[key].get("timeout") for key in vector_keys):
                missing.append("vector")
            elif outbox_health.get("vector", {}).get("unhealthy"):
                missing.append("vector")

        if require_graph and MemoryLayer.SEMANTIC in plan.layers:
            graph_result = fetch_results.get("semantic_graph", {})
            if graph_result.get("warning") or graph_result.get("timeout"):
                missing.append("graph")
            elif outbox_health.get("graph", {}).get("unhealthy"):
                missing.append("graph")
        return missing

    def _collect_candidates(self, fetch_results: Dict[str, Dict[str, Any]], structured_candidates: List[Dict[str, Any]]) -> Dict[tuple[str, str], HybridCandidate]:
        candidate_map: Dict[tuple[str, str], HybridCandidate] = {}
        for payload in list(fetch_results.values()) + [{"items": structured_candidates}]:
            for index, item in enumerate(payload.get("items", []), start=1):
                candidate = self._candidate_from_item(item, rank=index)
                if candidate is None:
                    continue
                key = (candidate.layer.value, candidate.record_id)
                if key in candidate_map:
                    candidate_map[key].merge(candidate)
                else:
                    candidate_map[key] = candidate
        return candidate_map

    def _candidate_from_item(self, item: Dict[str, Any], *, rank: int) -> Optional[HybridCandidate]:
        record_id = str(item.get("record_id") or item.get("id") or item.get("uuid") or "")
        layer = item.get("layer")
        if not record_id or not isinstance(layer, MemoryLayer):
            return None
        backend = str(item.get("backend", "lexical"))
        return HybridCandidate(
            record_id=record_id,
            layer=layer,
            payload=dict(item.get("payload") or {}),
            backend_scores={backend: float(item.get("backend_score", 0.0))},
            backend_ranks={backend: rank},
            sources=[backend],
            matched_terms=list(item.get("matched_terms") or []),
            match_reasons=list(item.get("match_reasons") or []),
            degraded_backends=list(item.get("degraded_backends") or []),
            freshness=float(item.get("freshness", 0.0)),
            usage_signal=float(item.get("usage_signal", 0.0)),
            exact_match=bool(item.get("exact_match")),
            path=list(item.get("path") or []) or None,
        )

    def _apply_rrf(self, plan: HybridSearchPlan, candidates: List[HybridCandidate]) -> None:
        k = self.weights.rrf_k
        for candidate in candidates:
            fused = 0.0
            for backend, rank in candidate.backend_ranks.items():
                weight = float(plan.weights.get(backend, 1.0))
                fused += weight * (1.0 / (k + max(rank, 1)))
            candidate.fused_score = fused

    def _rerank(self, plan: HybridSearchPlan, candidates: List[HybridCandidate]) -> List[HybridCandidate]:
        ranked = sorted(candidates, key=lambda item: item.fused_score, reverse=True)
        top = ranked[: plan.rerank_top_k]
        lower_query = plan.query.lower()
        query_tokens = set(plan.normalized_query.split())
        layer_priors = {
            QueryType.PROCEDURAL: {MemoryLayer.PROCEDURAL: 1.0, MemoryLayer.EPISODIC: 0.6, MemoryLayer.SEMANTIC: 0.5},
            QueryType.EPISODIC: {MemoryLayer.EPISODIC: 1.0, MemoryLayer.SEMANTIC: 0.6, MemoryLayer.PROCEDURAL: 0.5},
            QueryType.PREFERENCE: {MemoryLayer.USER_MODEL: 1.0},
            QueryType.RELATIONAL: {MemoryLayer.SEMANTIC: 1.0},
        }.get(plan.query_type, {})

        for candidate in top:
            indexed_text = str(candidate.payload.get("indexed_text", "")).lower()
            content = f"{candidate.payload.get('name', '')}\n{candidate.payload.get('content', '')}".lower()
            exact_bonus = 1.0 if candidate.exact_match or lower_query in content else 0.0
            token_hits = len(query_tokens.intersection(set(indexed_text.split()))) if query_tokens else 0
            overlap_bonus = min(1.0, token_hits / max(1, len(query_tokens))) if query_tokens else 0.0
            freshness_bonus = max(0.0, min(1.0, candidate.freshness))
            usage_bonus = max(0.0, min(1.0, candidate.usage_signal))
            layer_bonus = max(0.0, min(1.0, layer_priors.get(candidate.layer, 0.4)))
            graph_bonus = 1.0 if candidate.path else 0.0
            candidate.score_breakdown = {
                "fused_rrf": candidate.fused_score,
                "exact_or_phrase_match": exact_bonus,
                "token_overlap": overlap_bonus,
                "freshness_or_decay": freshness_bonus,
                "usage_signal": usage_bonus,
                "intent_layer_prior": layer_bonus,
                "graph_path_bonus": graph_bonus,
            }
            candidate.final_score = (
                0.50 * candidate.fused_score
                + 0.15 * exact_bonus
                + 0.10 * overlap_bonus
                + 0.10 * freshness_bonus
                + 0.10 * usage_bonus
                + 0.10 * layer_bonus
                + 0.05 * graph_bonus
            )

        top.sort(key=lambda item: item.final_score, reverse=True)
        return top + ranked[plan.rerank_top_k :]

    def _candidate_to_result(self, plan: HybridSearchPlan, candidate: HybridCandidate, degraded_backends: Iterable[str]) -> Dict[str, Any]:
        payload = dict(candidate.payload)
        result = {
            "uuid": payload.get("uuid", candidate.record_id),
            "layer": candidate.layer.value,
            "name": payload.get("name", ""),
            "content": payload.get("content", ""),
            "score": round(candidate.final_score or candidate.fused_score, 6),
            "metadata": dict(payload.get("metadata", {}) or {}),
            "source": payload.get("source", candidate.sources[0] if candidate.sources else "hybrid"),
            "sources": list(candidate.sources),
            "degraded_backends": sorted(set(candidate.degraded_backends + list(degraded_backends))) or None,
        }
        if plan.explain:
            result["score_breakdown"] = candidate.score_breakdown
            result["match_reasons"] = candidate.match_reasons or None
            result["path"] = candidate.path
        elif candidate.path:
            result["path"] = candidate.path
        return result

    def _group_results(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for result in results:
            grouped.setdefault(str(result.get("layer")), []).append(copy.deepcopy(result))
        return grouped
