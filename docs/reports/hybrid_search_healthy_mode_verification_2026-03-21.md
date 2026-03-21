# Synapse Hybrid Search Healthy-Mode Verification

Review date: 2026-03-21  
Scope: actual verification of `graph + vector` healthy mode using the current worktree  
Reviewer: Codex

## Executive Summary

Verdict for verified scope: Pass.

This verification pass exercised the current local worktree through a real `uvicorn` process with:
- `SYNAPSE_ENABLE_GRAPHITI=true`
- `SYNAPSE_ENABLE_QDRANT=true`
- live `FalkorDB` on `127.0.0.1:6379`
- live `Qdrant` on `127.0.0.1:6333`
- `SYNAPSE_SEARCH_ENGINE=hybrid_auto`

Headline result:
- `19/19` healthy-mode actual checks passed
- embedded `pre_deploy_smoke.py --require-graph --semantic-write-check` passed `49/49`

Important note:
- this report verifies the current worktree, not the older long-running Docker API container on port `8000`
- during this verification pass, three real healthy-mode defects were discovered and fixed before rerunning:
  - graph client was not wired into `LayerManager.semantic`
  - semantic graph outbox writes were dispatched on the wrong event loop
  - `GET /api/graph/nodes?query=...` could surface irrelevant graph hits before direct node matches

## Evidence

Primary verification script:
- [verify_hybrid_search_healthy_mode.py](/C:/Programing/PersonalAI/synapse/scripts/verify_hybrid_search_healthy_mode.py)

Evidence JSON:
- [hybrid_search_healthy_mode_verification_2026-03-21.json](/C:/Programing/PersonalAI/synapse/docs/reports/evidence/hybrid_search_healthy_mode_verification_2026-03-21.json)

Related safe-mode baseline report:
- [hybrid_search_actual_verification_2026-03-21.md](/C:/Programing/PersonalAI/synapse/docs/reports/hybrid_search_actual_verification_2026-03-21.md)

Key implementation references for the fixes made in this pass:
- [synapse_service.py](/C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L276)
- [semantic.py](/C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L95)
- [semantic.py](/C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L256)
- [synapse_service.py](/C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L2007)

## Environment Used

Healthy-mode runtime for this report:
- `SYNAPSE_ENABLE_GRAPHITI=true`
- `SYNAPSE_ENABLE_QDRANT=true`
- `SYNAPSE_SEARCH_ENGINE=hybrid_auto`
- `SYNAPSE_API_KEY=synapse-dev-key`
- `QDRANT_URL=http://127.0.0.1:6333`
- `FALKORDB_HOST=127.0.0.1`
- `FALKORDB_PORT=6379`
- `FALKORDB_DATABASE=user-bfipa`

Execution model:
- real `uvicorn` process started from the current repository contents
- isolated temporary `HOME` / `USERPROFILE`
- live external backends reused from the machine
- smoke and verification traffic used unique semantic tokens to avoid ambiguity

## Defects Found and Fixed During Verification

### 1. Graph client wiring into semantic hybrid search

Problem:
- `SynapseService` had a live `graphiti_client`
- `HybridSearchEngine` delegated graph candidate fetches through `LayerManager.semantic`
- but `LayerManager.semantic._graphiti` was still `None`

Effect:
- healthy mode showed `vector` working, while hybrid search still reported `graph backend unavailable`

Fix:
- `SynapseService.__init__()` now injects the `graphiti_client` into `self.layers.semantic` when needed in [synapse_service.py](/C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L276)

### 2. Semantic graph outbox loop affinity

Problem:
- graph outbox writes ran in a worker thread
- the worker used `asyncio.run()` / new event loops
- the `Graphiti` client had been created on the app loop

Effect:
- healthy-mode graph writes failed with `Future attached to a different loop`
- new semantic writes could reach SQLite/Qdrant while failing to persist to FalkorDB

Fix:
- `SemanticManager` now captures the app loop when available and dispatches graph outbox coroutines back onto that loop with `asyncio.run_coroutine_threadsafe()` in [semantic.py](/C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L95) and [semantic.py](/C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L256)

### 3. Graph node search route relevance

Problem:
- `search_nodes(query=...)` relied on `graphiti.search()` first
- that could return older edge hits unrelated to a newly created unique token

Effect:
- `/api/graph/nodes?query=<new-token>` could miss the fresh token even when FalkorDB already had matching nodes

Fix:
- `search_nodes()` now performs direct FalkorDB `name/summary` matching first, then falls back to `graphiti.search()` only if direct node lookup has no hit in [synapse_service.py](/C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L2007)

## Actual Checks Performed

All of the following passed:

| Check | Result | What was verified |
| --- | --- | --- |
| `health_http` | Pass | local `uvicorn` instance started and responded healthy |
| `system_status_http` | Pass | `GET /api/system/status` returned healthy status |
| `graph_component_healthy` | Pass | `falkordb` component reported `healthy` |
| `semantic_create_http` | Pass | semantic create succeeded against current worktree in healthy mode |
| `semantic_create_body` | Pass | semantic create returned persisted UUID |
| `graph_nodes_http` | Pass | graph node search endpoint returned `200` |
| `graph_nodes_token_match` | Pass | the newly written semantic token appeared in FalkorDB-backed node search |
| `graph_node_edges_http` | Pass | graph edge lookup endpoint returned `200` |
| `graph_node_edges_token_match` | Pass | the newly written graph edge fact contained the new token |
| `hybrid_auto_uses_all_backends` | Pass | `POST /api/memory/search` used `graph + lexical + vector` together with no degraded warning |
| `hybrid_strict_semantic_success` | Pass | `mode=hybrid_strict` semantic search succeeded with healthy graph/vector backends |
| `consult_hybrid_auto_success` | Pass | `POST /api/oracle/consult` used `graph + lexical + vector` in healthy mode |
| `cache_seed_search` | Pass | first non-explain search seeded query cache |
| `cache_repeat_search` | Pass | second identical search completed and was eligible for query-cache hit accounting |
| `system_stats_http` | Pass | `GET /api/system/stats` returned healthy-mode search telemetry |
| `system_stats_search_counts` | Pass | stats showed `backend_used:graph`, `backend_used:lexical`, `backend_used:vector`, and `cache_hit:query` |
| `pre_deploy_smoke_require_graph` | Pass | end-to-end smoke with `--require-graph --semantic-write-check` passed |
| `graph_node_and_edge_match_token` | Pass | graph node and graph edge payloads both contained the unique token from this run |
| `created_semantic_retrievable` | Pass | the semantic record created in this run was retrievable through hybrid search results |

## What the Actual Results Show

### 1. Full healthy-mode retrieval is working

Confirmed behavior:
- `POST /api/memory/search` in healthy mode used all three retrieval backends:
  - `graph`
  - `lexical`
  - `vector`
- response was not degraded
- graph-sourced results included real `path` data
- non-graph semantic record retrieval was also present

The evidence JSON shows:
- `used_backends=['graph', 'lexical', 'vector']`
- `degraded=False`

### 2. Semantic writes now persist to FalkorDB correctly

Confirmed behavior:
- a new semantic write created a graph node whose `name` matched the fresh token
- the related graph edge fact was visible through `/api/graph/nodes/{id}/edges`

Example verified fact from this run:
- `gvh59d2df80d29c is associated with semantic vector graph retrieval testing`

This is direct evidence that the graph outbox path is working after the event-loop fix.

### 3. Strict healthy mode now succeeds

Confirmed behavior:
- `mode=hybrid_strict`
- `query_type=semantic`
- `layers=['SEMANTIC']`

returned `200` in healthy mode, instead of degrading or failing.

This is the key difference between this report and the earlier safe-mode baseline report.

### 4. Search telemetry reflects real healthy-mode backend usage

Observed in `system/stats` from this run:
- `backend_used:graph >= 1`
- `backend_used:lexical >= 1`
- `backend_used:vector >= 1`
- `cache_hit:query >= 1`

The recorded stats snapshot in the evidence JSON showed:
- `backend_used:graph = 5`
- `backend_used:lexical = 5`
- `backend_used:vector = 5`
- `cache_hit:query = 1`

### 5. Release smoke now covers healthy graph mode successfully

The embedded smoke run executed:

```bash
python scripts/pre_deploy_smoke.py \
  --base-url http://127.0.0.1:<temp-port> \
  --api-key synapse-dev-key \
  --require-graph \
  --semantic-write-check
```

Smoke result:
- `49/49` checks passed

This confirms the current smoke gate is usable for healthy-mode release verification on this machine.

## Boundaries / Not Covered by This Report

The following are still outside this specific report:
- MCP runtime end-to-end verification
- load / concurrency soak testing
- long-duration outbox lag behavior over hours
- staged deployment validation in a non-local environment

## Overall Assessment

For the verified healthy-mode scope, the current Synapse worktree is now behaving like a real hybrid search runtime:
- semantic writes persist to SQLite, Qdrant, and FalkorDB paths
- hybrid search uses `lexical + vector + graph`
- strict semantic mode succeeds when the backends are healthy
- system stats and smoke coverage reflect real backend usage

Accurate statement as of this report:
- `safe-mode baseline`: verified in the earlier report
- `graph + vector healthy mode`: now verified and passing
- `release smoke for healthy mode`: verified and passing
- `MCP end-to-end`: still not verified in this pass
