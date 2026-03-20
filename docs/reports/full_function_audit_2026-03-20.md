# Synapse Full Function Audit

Review date: 2026-03-20
Scope: all exposed API functions, core runtime behavior, production readiness plan
Reviewer: Codex

## Executive Summary

Verdict: Not ready for production.

High-level state:
- Some APIs work and return structurally valid responses.
- Several core write/update paths are broken.
- API auth is not enforced.
- Test harness is broken, so current automation does not protect against regressions.

This report focuses on:
- full endpoint inventory
- real smoke-check status where possible
- code-backed issue mapping
- phased remediation plan

Verification legend:
- `Dynamic`: executed through FastAPI `TestClient` with real `SynapseService` and temp SQLite backends
- `Static`: evaluated from code paths only
- `Partial`: endpoint returns but contract/data correctness is incomplete

## Cross-Cutting Blockers

### 1. Authentication is not enforced

Status: Broken
Verification: Dynamic

Evidence:
- API accepts requests without a valid API key.
- App mounts CORS and error middleware, but not `AuthMiddleware`.

References:
- [api/main.py#L78](C:/Programing/PersonalAI/synapse/api/main.py#L78)
- [api/middleware/auth.py#L14](C:/Programing/PersonalAI/synapse/api/middleware/auth.py#L14)

### 2. API test harness is broken

Status: Broken
Verification: Dynamic + Static

Evidence:
- `MockSynapseService` is imported by tests but does not exist.
- API tests fail before execution.

References:
- [api/tests/conftest.py#L9](C:/Programing/PersonalAI/synapse/api/tests/conftest.py#L9)

### 3. Startup/config is fragile

Status: Partial
Verification: Dynamic

Evidence:
- Current environment failed import until `DEBUG` was forced to a valid boolean.

References:
- [api/config.py#L23](C:/Programing/PersonalAI/synapse/api/config.py#L23)

## Endpoint Inventory

### Root and Health

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/` | OK | Dynamic | Returns API metadata |
| GET | `/health` | OK | Dynamic | Returns health payload |

### Identity

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/api/identity/` | OK | Dynamic | Returns current identity |
| PUT | `/api/identity/` | OK | Dynamic | Sets identity context |
| DELETE | `/api/identity/` | OK | Dynamic | Clears identity context |
| GET | `/api/identity/preferences` | OK | Dynamic | Returns normalized preferences |
| PUT | `/api/identity/preferences` | Partial | Dynamic | Updates data, but response omits `user_id` and `updated_at` |

Identity issue reference:
- [api/routes/identity.py#L141](C:/Programing/PersonalAI/synapse/api/routes/identity.py#L141)

### Memory

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/api/memory/` | OK | Dynamic | Lists procedural + episodic data |
| GET | `/api/memory/{id}` | OK | Dynamic | Worked for procedure and episode |
| POST | `/api/memory/` procedural content | Partial | Dynamic | Insert succeeds but response returns empty UUID |
| POST | `/api/memory/` episodic content | Broken | Dynamic | Returns `500` |
| POST | `/api/memory/search` | OK | Dynamic | Unfiltered search returns results |
| POST | `/api/memory/search` with `layers` | Broken | Dynamic | Filtered search returns empty results due enum mismatch |
| POST | `/api/memory/consolidate` | OK | Dynamic | Dry-run worked |
| PUT | `/api/memory/{id}` procedural | Broken | Dynamic | Returns `500` |
| PUT | `/api/memory/{id}` episodic | Broken | Dynamic | Returns `500` |
| DELETE | `/api/memory/{id}` | OK | Dynamic | Procedure delete worked |

Key issues:
- Episodic create path passes unsupported args to `record_episode()`
- Memory create does not return real top-level `uuid`
- Layer reported to client can differ from actual storage layer
- Filtered search breaks on API/core enum mismatch
- Update path calls missing or incompatible methods

References:
- [synapse/services/synapse_service.py#L305](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L305)
- [synapse/services/synapse_service.py#L423](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L423)
- [api/routes/memory.py#L111](C:/Programing/PersonalAI/synapse/api/routes/memory.py#L111)
- [api/routes/memory.py#L132](C:/Programing/PersonalAI/synapse/api/routes/memory.py#L132)
- [api/routes/memory.py#L158](C:/Programing/PersonalAI/synapse/api/routes/memory.py#L158)
- [synapse/layers/manager.py#L278](C:/Programing/PersonalAI/synapse/synapse/layers/manager.py#L278)
- [synapse/services/synapse_service.py#L1309](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L1309)
- [synapse/layers/episodic.py#L959](C:/Programing/PersonalAI/synapse/synapse/layers/episodic.py#L959)
- [api/models/memory.py#L12](C:/Programing/PersonalAI/synapse/api/models/memory.py#L12)
- [synapse/layers/types.py#L13](C:/Programing/PersonalAI/synapse/synapse/layers/types.py#L13)

### Procedures

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/api/procedures/` | OK | Dynamic | List worked |
| POST | `/api/procedures/` | Partial | Dynamic | Create works, but response UUID is `"new"` instead of real ID |
| POST | `/api/procedures/{id}/success` | Partial | Dynamic | Success increments count, but response `trigger` is the path param UUID, not the procedure trigger |
| GET | `/api/procedures/{id}` | OK | Dynamic | Read worked |
| PUT | `/api/procedures/{id}` | Broken | Dynamic | Returns `500` because update method is missing |
| DELETE | `/api/procedures/{id}` | OK | Dynamic | Delete worked |

References:
- [api/routes/procedures.py#L74](C:/Programing/PersonalAI/synapse/api/routes/procedures.py#L74)
- [api/routes/procedures.py#L95](C:/Programing/PersonalAI/synapse/api/routes/procedures.py#L95)
- [api/routes/procedures.py#L128](C:/Programing/PersonalAI/synapse/api/routes/procedures.py#L128)
- [synapse/services/synapse_service.py#L757](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L757)
- [synapse/services/synapse_service.py#L2359](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L2359)

### Episodes

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/api/episodes/` | OK | Dynamic | Local episodic list worked |
| GET | `/api/episodes/{id}` | OK | Dynamic | Local episodic read worked |
| DELETE | `/api/episodes/{id}` | OK | Dynamic | Local episodic delete worked |

### Oracle

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| POST | `/api/oracle/consult` | OK | Dynamic | Procedural consult worked |
| POST | `/api/oracle/reflect` | OK | Dynamic | Returned procedure + episode insights |
| POST | `/api/oracle/analyze` | OK | Dynamic | Returned pattern summary |

Comment:
- Oracle endpoints are among the healthier areas in local-only mode.

### System

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/api/system/status` | OK | Dynamic | Returns degraded status when graph is unavailable |
| GET | `/api/system/stats` | OK | Dynamic | Returns storage/memory counts |
| POST | `/api/system/maintenance` | Partial | Dynamic | Returns `200`, but `purge_expired` becomes “Unknown maintenance action” because API enum/value case does not match service logic |
| DELETE | `/api/system/graph` | Broken | Dynamic | Returns `500`; service has no `clear_graph()` method |

References:
- [api/routes/system.py#L73](C:/Programing/PersonalAI/synapse/api/routes/system.py#L73)
- [synapse/services/synapse_service.py#L2505](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L2505)

### Graph

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/api/graph/nodes` | OK | Dynamic | Returns empty list when no graph driver |
| GET | `/api/graph/nodes/{id}` | OK | Dynamic | Returns `404` if not found |
| GET | `/api/graph/nodes/{id}/edges` | OK | Dynamic | Returns empty list when no driver |
| GET | `/api/graph/edges` | OK | Dynamic | Returns empty list when no driver |
| GET | `/api/graph/edges/{id}` | OK | Dynamic | Returns `404` if not found |
| DELETE | `/api/graph/nodes/{id}` | Partial | Dynamic | Returns success message even when no graph driver exists |
| DELETE | `/api/graph/edges/{id}` | Partial | Dynamic | Returns success message even when no graph driver exists |

References:
- [synapse/services/synapse_service.py#L2056](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L2056)
- [synapse/services/synapse_service.py#L2081](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L2081)

### Feed

| Method | Path | Status | Verification | Notes |
|---|---|---|---|---|
| GET | `/api/feed/` | Broken | Dynamic | Returned `500` due naive/aware datetime comparison during sort |
| GET | `/api/feed/stream` | Unverified | Static | Route exists; SSE behavior not fully smoke-tested in this audit |

References:
- [api/routes/feed.py#L141](C:/Programing/PersonalAI/synapse/api/routes/feed.py#L141)
- [api/routes/feed.py#L145](C:/Programing/PersonalAI/synapse/api/routes/feed.py#L145)

## Core Storage and Runtime Notes

### SQLite runtime state from actual local storage

Observed under `C:\\Users\\bfipa\\.synapse`:
- `user_model.db`: 20 rows
- `procedural.db`: 356 rows
- `episodic.db`: 0 rows

Interpretation:
- Procedural and user-model persistence are active.
- Episodic persistence is effectively absent in current runtime data.

### Semantic memory state

Status: Partial to Broken
Verification: Dynamic + Static

Findings:
- Semantic writes rely on Qdrant/Graphiti path.
- Qdrant point IDs generated by semantic layer are not Qdrant-compatible in observed testing.
- Successful semantic add does not guarantee retrievable data.

References:
- [synapse/layers/semantic.py#L268](C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L268)
- [synapse/layers/semantic.py#L284](C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L284)

## Status Summary by Area

| Area | Overall Status | Comment |
|---|---|---|
| Root/Health | OK | Basic app boot and health payload work |
| Identity | Partial | Core functions work, response contract incomplete on update |
| Memory | Broken | Core create/update/search contract issues |
| Procedures | Partial | CRUD mostly works except update and response contract issues |
| Episodes | OK | Local episode list/get/delete work |
| Oracle | OK | Works in local-only mode |
| System | Partial | Status/stats work, maintenance mapping and clear-graph are broken |
| Graph | Partial | Read endpoints degrade gracefully; delete semantics are misleading |
| Feed | Broken | Feed listing fails; stream not verified |
| Auth | Broken | Security blocker |
| Tests | Broken | Automation blocker |

## Required Remediation Plan

### Phase 0: Security and Runtime Safety

Priority: P0

Tasks:
1. Mount `AuthMiddleware` in the FastAPI app.
2. Add auth tests for valid key, missing key, and invalid key.
3. Harden settings parsing for `DEBUG` and other env values.
4. Add startup validation that reports missing/invalid configuration clearly.

Exit criteria:
- Protected routes reject missing/wrong API keys.
- App starts reliably with validated config.

### Phase 1: API Contract Correctness

Priority: P0

Tasks:
1. Make create endpoints return real IDs.
2. Return the actual persisted layer from memory create.
3. Normalize API/core layer enum values to one canonical scheme.
4. Fix preferences update response to include `user_id` and `updated_at`.
5. Fix procedure success response to return the real trigger, not the path UUID.

Exit criteria:
- Response payloads match persisted state.
- Client can trust returned identifiers and layer metadata.

### Phase 2: Broken CRUD Paths

Priority: P0

Tasks:
1. Fix episodic create path in `SynapseService._route_to_layer()`.
2. Fix episodic update path to call `update_episode()` with supported args only.
3. Implement `ProceduralManager.update_procedure()` or remove/update the API contract.
4. Fix `/api/system/graph` by implementing `clear_graph()` or disabling the endpoint until supported.

Exit criteria:
- All advertised CRUD endpoints execute successfully.

### Phase 3: Search, Feed, and Maintenance Correctness

Priority: P1

Tasks:
1. Fix memory filtered search enum mismatch.
2. Fix maintenance action mapping between API enum values and service logic.
3. Normalize all feed timestamps to timezone-aware datetimes before sorting.
4. Decide graph no-driver semantics: return `503` or clear degraded response instead of fake delete success.

Exit criteria:
- Search filters work.
- Feed list works.
- Maintenance actions execute intended behavior.

### Phase 4: Semantic and Graph Reliability

Priority: P1

Tasks:
1. Make semantic entity IDs compatible with Qdrant requirements.
2. Define durable fallback when Graphiti/Qdrant is absent.
3. Add graph integration tests for driver-present and driver-absent modes.

Exit criteria:
- Semantic writes are retrievable and durable in supported deployment modes.

### Phase 5: Automated Verification

Priority: P0

Tasks:
1. Replace broken `MockSynapseService` test fixture.
2. Add real API smoke tests for all non-stream endpoints.
3. Add contract tests for IDs, layer values, and error semantics.
4. Add regression tests for:
   - episodic create
   - memory filtered search
   - procedures update
   - system maintenance
   - feed list
   - auth enforcement

Exit criteria:
- Test suite executes cleanly.
- Core regressions are covered in CI.

## Recommended Work Order

1. Auth enforcement
2. Memory create/update correctness
3. Procedure update support
4. Search/filter/feed fixes
5. System clear-graph and maintenance alignment
6. Semantic/Qdrant compatibility
7. Full automated test recovery

## Final Decision

Do not deploy Synapse to production yet.

Reason:
- There are still P0 issues in security, CRUD correctness, and contract reliability.

The previous focused report remains relevant for memory persistence details:
- [production_readiness_review_2026-03-20.md](C:/Programing/PersonalAI/synapse/docs/reports/production_readiness_review_2026-03-20.md)
