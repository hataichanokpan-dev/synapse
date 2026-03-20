# Synapse Production Readiness Review

Review date: 2026-03-20
Scope: memory persistence, API behavior, real storage verification, production readiness
Reviewer: Codex

## Executive Summary

Verdict: Not ready for production.

Current state:
- Procedural memory can be written to SQLite and read back.
- Episodic memory creation is broken in the real service path.
- Memory create responses are unreliable and can report the wrong layer.
- Layer-filtered search is broken.
- API authentication is not enforced.
- Automated API verification is broken, so current tests do not prove production readiness.

Overall assessment:
- Core memory functionality is only partially working.
- The system is not safe to deploy as a production AI memory service until critical issues are fixed and retested.

## Critical Findings

### 1. API authentication is not enforced

Severity: Critical

Evidence:
- The app mounts CORS and error middleware only.
- `AuthMiddleware` exists but is not added to the FastAPI app.

References:
- [api/main.py#L78](C:/Programing/PersonalAI/synapse/api/main.py#L78)
- [api/middleware/auth.py#L14](C:/Programing/PersonalAI/synapse/api/middleware/auth.py#L14)

Verified behavior:
- `GET /api/memory/` returned `200` without `X-API-Key`.
- `GET /api/memory/` also returned `200` with a wrong API key.

Impact:
- Any client can access the memory API.
- This is a release blocker for production.

### 2. Episodic memory creation fails in the real path

Severity: Critical

Evidence:
- `SynapseService._route_to_layer()` calls `record_episode()` with unsupported arguments: `source` and `metadata`.
- `LayerManager.record_episode()` does not accept those arguments.

References:
- [synapse/services/synapse_service.py#L423](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L423)
- [synapse/layers/manager.py#L166](C:/Programing/PersonalAI/synapse/synapse/layers/manager.py#L166)

Verified behavior:
- Manual `POST /api/memory/` with episodic content returned `500 Internal Server Error`.
- Direct service test raised `TypeError: LayerManager.record_episode() got an unexpected keyword argument 'source'`.
- Runtime `episodic.db` currently contains `0` rows.

Impact:
- One of the core memory layers cannot be created through the main API path.
- Production memory retention is incomplete.

### 3. Memory create response can lie about layer and does not return a real UUID

Severity: Critical

Evidence:
- The API request model supports `layer`, but the route does not pass it to the service.
- The service auto-classifies and returns lowercase layer names.
- The API route then falls back to the requested layer if enum parsing fails.
- The route returns `uuid=result.get("uuid", "")`, but the service does not include top-level `uuid`.

References:
- [api/models/memory.py#L22](C:/Programing/PersonalAI/synapse/api/models/memory.py#L22)
- [api/routes/memory.py#L111](C:/Programing/PersonalAI/synapse/api/routes/memory.py#L111)
- [api/routes/memory.py#L132](C:/Programing/PersonalAI/synapse/api/routes/memory.py#L132)
- [synapse/services/synapse_service.py#L305](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L305)

Verified behavior:
- Request: `layer=EPISODIC`, content: procedural text.
- Response: `layer=EPISODIC`, `uuid=""`.
- Actual database state: row inserted into `procedural.db`, nothing inserted into `episodic.db`.

Impact:
- Clients cannot trust API responses.
- Downstream systems may store wrong IDs and wrong layer metadata.

### 4. Layer-filtered memory search is broken

Severity: High

Evidence:
- API layer enum uses uppercase values.
- Core layer enum uses lowercase values.
- Search passes uppercase strings from the API into core layer filtering logic.
- Core search checks enum membership, so filtered search does not match.

References:
- [api/models/memory.py#L12](C:/Programing/PersonalAI/synapse/api/models/memory.py#L12)
- [synapse/layers/types.py#L13](C:/Programing/PersonalAI/synapse/synapse/layers/types.py#L13)
- [api/routes/memory.py#L158](C:/Programing/PersonalAI/synapse/api/routes/memory.py#L158)
- [synapse/layers/manager.py#L278](C:/Programing/PersonalAI/synapse/synapse/layers/manager.py#L278)

Verified behavior:
- Search without `layers` found the inserted procedure.
- Search with `layers=["PROCEDURAL"]` returned zero results for the same data.

Impact:
- API search filters are not reliable.
- Feature behavior does not match the contract.

## Major Findings

### 5. Semantic memory persistence is not reliable in the current setup

Severity: High

Evidence:
- Semantic entities use non-UUID Qdrant IDs like `entity_python_fact_<timestamp>`.
- Qdrant rejected the write in manual verification.
- Immediate semantic search after add returned no results.

References:
- [synapse/layers/semantic.py#L268](C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L268)
- [synapse/layers/semantic.py#L284](C:/Programing/PersonalAI/synapse/synapse/layers/semantic.py#L284)

Verified behavior:
- `add_memory()` for semantic content returned success.
- Follow-up semantic search returned no records.
- Qdrant reported invalid point ID format.

Impact:
- Semantic memory is not dependable unless storage compatibility is fixed.

### 6. API test harness is broken and does not validate the real system

Severity: High

Evidence:
- Test fixture imports `MockSynapseService`, but that symbol does not exist.
- With the current environment, API imports also fail if `DEBUG=release`.

References:
- [api/tests/conftest.py#L9](C:/Programing/PersonalAI/synapse/api/tests/conftest.py#L9)
- [api/config.py#L23](C:/Programing/PersonalAI/synapse/api/config.py#L23)

Verified behavior:
- `pytest api/tests/test_memory.py -q` failed before running tests.
- `pytest api/tests/test_memory_real.py -q` failed before running tests.

Impact:
- Current automated tests do not prove the memory system is production-ready.

## Secondary Findings

### 7. Procedure update path is broken

Severity: Medium

Evidence:
- Service calls `self.layers.procedural.update_procedure(...)`.
- `ProceduralManager` does not implement `update_procedure`.

References:
- [synapse/services/synapse_service.py#L2359](C:/Programing/PersonalAI/synapse/synapse/services/synapse_service.py#L2359)
- [api/routes/procedures.py#L158](C:/Programing/PersonalAI/synapse/api/routes/procedures.py#L158)
- [synapse/layers/procedural.py#L575](C:/Programing/PersonalAI/synapse/synapse/layers/procedural.py#L575)

Verified behavior:
- Manual `PUT /api/procedures/{id}` returned `500`.

Impact:
- CRUD support is incomplete.

### 8. API startup is sensitive to invalid environment values

Severity: Medium

Evidence:
- `debug` is typed as boolean.
- Current environment contained `DEBUG=release`, which fails validation.

References:
- [api/config.py#L23](C:/Programing/PersonalAI/synapse/api/config.py#L23)

Verified behavior:
- Importing `api.deps` failed until `DEBUG` was forced to `false`.

Impact:
- Deployment can fail before the service starts.

## Real Storage Verification

Verified local runtime storage under `C:\\Users\\bfipa\\.synapse`:

- `user_model.db`
  - table `user_models`: 20 rows
- `procedural.db`
  - table `procedures`: 356 rows
- `episodic.db`
  - table `episodes`: 0 rows
  - table `episodes_archive`: 0 rows

Interpretation:
- Procedural and user-model data exist in local SQLite.
- Episodic memory is effectively not being retained in the current runtime database.

## Functional Status Summary

### Working

- Procedural memory insert to SQLite
- Procedural memory list/read in basic cases
- Unfiltered memory search can return procedural results
- User-model SQLite storage exists

### Not Working Correctly

- Episodic memory create through the main API/service path
- Correct UUID return from memory create
- Correct layer reporting from memory create
- Layer-filtered memory search
- Procedure update endpoint
- API authentication enforcement
- API test suite execution
- Reliable semantic persistence in current setup

## Production Decision

Decision: Do not deploy to production.

Reason:
- Critical security gap
- Broken core memory layer
- Incorrect API contract behavior
- Broken automated verification

## Required Fix Order

1. Enforce API authentication in the FastAPI app.
2. Fix episodic create path so real episode rows are written successfully.
3. Fix `POST /api/memory/` to return real `uuid` and actual persisted `layer`.
4. Normalize layer enums between API and core logic.
5. Fix filtered search.
6. Fix procedure update support.
7. Repair the API test harness and rerun real integration tests.
8. Fix semantic storage compatibility with Qdrant or define a supported fallback.

## Conclusion

Synapse is not ready yet as a production AI memory system.

The strongest positive signal is that procedural memory can be persisted to SQLite and read back. The strongest negative signals are that episodic memory creation fails, authentication is missing, search filtering is broken, and the API cannot currently be trusted to return correct create metadata.
