# Synapse Hybrid Search Actual Verification

Review date: 2026-03-21  
Scope: actual verification of the newly added hybrid-search functionality  
Reviewer: Codex

## Executive Summary

Verdict for verified scope: Pass in safe-mode baseline.

Actual verification completed successfully for the newly added hybrid-search behavior in these runtime paths:
- direct service-level execution with real SQLite-backed layer managers
- real HTTP API execution through a temporary `uvicorn` server
- end-to-end smoke verification using `scripts/pre_deploy_smoke.py --semantic-write-check`

Headline result:
- `24/24` actual verification checks passed in the dedicated verification runner
- `47/47` checks passed in the end-to-end smoke run embedded in that verification

Important boundaries:
- This report verifies the `safe-mode baseline` only:
  - `SYNAPSE_ENABLE_GRAPHITI=false`
  - `SYNAPSE_ENABLE_QDRANT=false`
  - `SYNAPSE_SEARCH_ENGINE=hybrid_auto`
- This report does **not** prove full healthy-mode behavior for real `graph + vector` backends.
- This report does **not** prove MCP runtime behavior end-to-end because the MCP module import was blocked on this Windows host by an external dependency import hang.

## Evidence

Primary verification script:
- [scripts/verify_hybrid_search_actual.py](/C:/Programing/PersonalAI/synapse/scripts/verify_hybrid_search_actual.py)

Evidence JSON:
- [hybrid_search_actual_verification_2026-03-21.json](/C:/Programing/PersonalAI/synapse/docs/reports/evidence/hybrid_search_actual_verification_2026-03-21.json)

Key implementation references:
- [engine.py](/C:/Programing/PersonalAI/synapse/synapse/search/engine.py#L35)
- [semantic_store.py](/C:/Programing/PersonalAI/synapse/synapse/layers/semantic_store.py#L44)
- [synapse_service.py](/C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L241)
- [memory.py](/C:/Programing/PersonalAI/synapse/api/models/memory.py#L59)
- [oracle.py](/C:/Programing/PersonalAI/synapse/api/models/oracle.py#L34)
- [pre_deploy_smoke.py](/C:/Programing/PersonalAI/synapse/scripts/pre_deploy_smoke.py#L184)

## Method

The verification used two layers of actual execution:

1. Service-level actual checks
- Real `LayerManager`, `EpisodicManager`, `ProceduralManager`, `SemanticManager`, `WorkingManager`
- Real temporary SQLite databases
- Real `SynapseService`
- Graph and vector disabled to force safe-mode hybrid behavior

2. API-level actual checks
- Real `uvicorn` process serving `api.main:app`
- Real HTTP requests using the standard library
- Temporary isolated `HOME` / `USERPROFILE`
- Real smoke run through `scripts/pre_deploy_smoke.py --semantic-write-check`

## Environment Used

Safe-mode runtime for this report:
- `SYNAPSE_ENABLE_GRAPHITI=false`
- `SYNAPSE_ENABLE_QDRANT=false`
- `SYNAPSE_SEARCH_ENGINE=hybrid_auto`
- `SYNAPSE_API_KEY=synapse-dev-key`

Isolation approach:
- service-level writes used temporary directories
- API-level server used temporary home storage
- no verification in this report wrote to the normal user `~/.synapse` store

## Actual Checks Performed

### Service-Level Checks

All of the following passed:

| Check | Result | What was verified |
| --- | --- | --- |
| `request_model_default_mode_env` | Pass | `MemorySearchRequest` and `ConsultRequest` default mode follow `SYNAPSE_SEARCH_ENGINE` |
| `weights_file_load` | Pass | `SearchWeights` loads `config/hybrid_weights.yaml` and returns expected weights |
| `service_search_default_hybrid` | Pass | `SynapseService.search_memory()` defaults to `hybrid_auto`, returns ranked results, uses lexical backend, and injects `pinned_context` from working memory |
| `service_consult_default_hybrid` | Pass | `SynapseService.consult()` defaults to `hybrid_auto` and returns ranked results plus summary |
| `service_search_default_legacy_env` | Pass | Service default mode flips to `legacy` when env is set accordingly |
| `cache_invalidation_after_write` | Pass | Query cache is invalidated after a matching memory write and the new item becomes visible immediately |
| `query_cache_hit_recorded` | Pass | Repeat search records query-cache hits in hybrid telemetry |
| `timeout_budget_degrades_request` | Pass | Forced slow backend causes degraded partial response with timeout warnings rather than hanging |
| `strict_semantic_fails_without_graph` | Pass | `hybrid_strict` with semantic query fails cleanly when graph backend is unavailable |
| `semantic_projection_survives_reopen` | Pass | semantic lexical search still works after reopening the SQLite projection store |
| `system_stats_expose_search_and_projection` | Pass | `get_system_stats()` exposes hybrid search telemetry and semantic projection stats |

### API-Level Checks

All of the following passed:

| Check | Result | What was verified |
| --- | --- | --- |
| `api_create_episode` | Pass | real `POST /api/memory/` episodic create |
| `api_create_procedure` | Pass | real `POST /api/procedures/` create |
| `api_create_semantic` | Pass | real `POST /api/memory/` semantic create |
| `api_search_default_mode` | Pass | `POST /api/memory/search` works without explicitly sending mode |
| `api_search_default_mode_body` | Pass | response includes `mode_used=hybrid_auto`, `query_type_detected`, `used_backends`, and explain metadata |
| `api_consult_default_mode` | Pass | `POST /api/oracle/consult` works without explicitly sending mode |
| `api_consult_default_mode_body` | Pass | consult returns `ranked_results`, grouped summaries, and hybrid metadata |
| `api_strict_semantic_failure` | Pass | `POST /api/memory/search` with `mode=hybrid_strict` and `query_type=semantic` returns `503` with degraded backend details |
| `api_semantic_lexical_search` | Pass | semantic search works through the API in safe mode |
| `api_semantic_lexical_search_body` | Pass | semantic create is immediately retrievable through lexical semantic search |
| `api_system_stats` | Pass | `GET /api/system/stats` returns search metrics |
| `api_system_stats_body` | Pass | stats payload includes query counts and nested semantic projection data |
| `pre_deploy_smoke_semantic_write` | Pass | `scripts/pre_deploy_smoke.py --semantic-write-check` passed end-to-end |

## What the Actual Results Show

### 1. Hybrid search works as the default runtime in safe mode

Confirmed behaviors:
- default request model mode respects `SYNAPSE_SEARCH_ENGINE`
- service and API default to `hybrid_auto` under safe-mode configuration
- ranked results and grouped layer summaries are returned consistently
- explain metadata is included when requested

### 2. Safe-mode degradation behaves correctly

Observed behavior:
- with graph disabled, hybrid responses are still usable
- responses carry `degraded=true` and `warnings=["graph backend unavailable"]`
- strict semantic path fails cleanly when graph is required

This is the expected safe-mode behavior for the current design.

### 3. Semantic lexical durability works

Confirmed behavior:
- semantic create writes durable state into SQLite projection
- lexical semantic search retrieves the new semantic item immediately
- reopening the semantic store does not destroy lexical searchability

This directly validates the `SQLite first` baseline behavior and the FTS rebuild fix in [semantic_store.py](/C:/Programing/PersonalAI/synapse/synapse/layers/semantic_store.py#L51).

### 4. Cache and timeout logic work in real execution

Confirmed behavior:
- repeated identical searches register query-cache hits
- new writes invalidate prior cache state
- artificially slowed backend fetchers degrade instead of blocking the request

This validates the runtime behavior in [engine.py](/C:/Programing/PersonalAI/synapse/synapse/search/engine.py#L64), [engine.py](/C:/Programing/PersonalAI/synapse/synapse/search/engine.py#L408), and [engine.py](/C:/Programing/PersonalAI/synapse/synapse/search/engine.py#L483).

## Smoke Verification

The embedded smoke run executed:
- `python scripts/pre_deploy_smoke.py --base-url <temp-uvicorn> --api-key synapse-dev-key --semantic-write-check`

Smoke result:
- `47/47` checks passed
- this included the newly added hybrid-search, consult, search-stats, and semantic-write smoke coverage

## Blocked / Not Verified in This Report

### 1. MCP runtime path

Status: Blocked on this host

Reason:
- importing [graphiti_mcp_server.py](/C:/Programing/PersonalAI/synapse/synapse/mcp_server/src/graphiti_mcp_server.py) triggered an external dependency import chain that hung in `platform._wmi_query` on this Windows machine
- the hang occurred in third-party import code (`rich/httpx/openai/graphiti_core` path), before actual MCP hybrid-search logic could be exercised

Impact:
- the MCP wrappers `search_memory_layers()` and `synapse_consult()` are **not** actually verified by this report
- this is a verification gap, not direct evidence of a Synapse logic defect

### 2. Full graph/vector healthy-mode verification

Status: Not covered

Not verified here:
- real `Qdrant` retrieval returning hybrid vector candidates
- real `Graphiti` graph retrieval participating in fused ranking
- `hybrid_strict` behavior with healthy graph/vector backends
- graph neighborhood cache behavior with a live graph backend

## Overall Assessment

For the verified safe-mode scope, the new hybrid-search functionality is working correctly.

Accurate statement as of this report:
- `service-level hybrid runtime`: verified and passing
- `API-level hybrid runtime`: verified and passing
- `semantic SQLite projection baseline`: verified and passing
- `timeout/cache/degraded behavior`: verified and passing
- `MCP direct runtime`: not verified in this pass
- `full graph/vector healthy mode`: not verified in this pass

## Recommended Next Steps

1. Run a second actual verification pass in a healthy `graph + vector` environment.
2. Add an MCP-specific verification path that avoids the current Windows import hang.
3. If this project will claim `full hybrid search`, do not make that claim until step 1 is complete.
