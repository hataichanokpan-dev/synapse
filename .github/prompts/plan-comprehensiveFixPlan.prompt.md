# Synapse Comprehensive Fix & Implementation Plan

> **Generated**: 2026-03-16  
> **By**: QA Tester (AI)  
> **Based on**: Gap Analysis Report + MCP Tools Test Report + QA Test Plan + Codebase Audit  
> **Status**: Ready for Execution

---

## Executive Summary

| Metric | ค่า |
|--------|-----|
| **Unit Tests (63/63)** | ✅ PASS ทั้งหมด — แต่ส่วนใหญ่ใช้ mock, ไม่ได้ทดสอบ logic จริง |
| **MCP Live Tests (15/16)** | ⚠️ 1 SKIPPED (`delete_episode` — no UUID available) |
| **MCP Tools Test Report** | ❌ 5/15 tools encoding error (Thai NLP) — **แต่ JSON report ล่าสุดแสดง 15/16 pass** |
| **Gap Analysis Gaps** | 14 gaps (3 P0, 4 P1, 4 P2, 3 P3) |
| **Test Coverage ที่ขาด** | Decay, Archive, TTL, Sync Queue, Thai NLP unit tests |
| **Estimated Total Work** | **140-220 hours** |

### สถานะปัจจุบัน vs เป้าหมาย

```
ตอนนี้: "Bug Fix Phase Complete" — 63 unit tests pass
       MCP Server ทำงานได้ — 15/16 tools respond correctly
       ⚠️ แต่ยังไม่ Production Ready

เป้าหมาย: Production Ready — ทุก layer มี MCP tools, error handling ครบ,
          tests ครอบคลุม, documentation สมบูรณ์
```

---

## Work Breakdown — 7 Work Packages

### ภาพรวม

| WP | ชื่อ | Priority | Est. Hours | Files | Dependencies |
|----|------|----------|-----------|-------|-------------|
| WP-1 | Thai Encoding Fix | P0 | 2-4 | 1 | None |
| WP-2 | MCP Layer Coverage (L1/L2/L5 Tools) | P0 | 10-16 | 2 | None |
| WP-3 | Identity Model + Oracle Tools | P0 | 14-21 | 3 | WP-2 |
| WP-4 | API Completeness + Error Handling | P1 | 20-30 | 3 | WP-2 |
| WP-5 | Working Memory Session Persistence | P1 | 10-15 | 1 | None |
| WP-6 | Comprehensive Test Suite | P1 | 24-36 | 2-3 | WP-1~5 |
| WP-7 | Config, Docs, Security, Performance | P2-P3 | 30-48 | 8-12 | WP-1~6 |
| | **TOTAL** | | **110-170** | | |

---

## WP-1: Thai Encoding Fix (P0 Critical)

> **Gap**: Gap 11.5 จาก Gap Analysis  
> **Problem**: 5 Thai NLP tools มี encoding error ตาม MCP Tools Test Report  
> **หมายเหตุ**: `mcp_test_report.json` ล่าสุด (16/16 excl. skip) อาจ fix แล้ว — **ต้อง verify**

### สิ่งที่ต้องทำ

| # | Task | File | Detail |
|---|------|------|--------|
| 1.1 | Verify Thai encoding ปัจจุบัน | `thai_nlp_tools.py` | รัน MCP server + ส่ง Thai text ไปทุก tool |
| 1.2 | Fix encoding ถ้ายังมีปัญหา | `thai_nlp_tools.py` | Ensure UTF-8 ใน response serialization |
| 1.3 | เพิ่ม charset header | `graphiti_mcp_server.py` | `Content-Type: application/json; charset=utf-8` |

### Acceptance Criteria
- [ ] `search_memory_layers` กับ Thai query ไม่ error
- [ ] `preprocess_for_extraction` กับ Thai text return ผลลัพธ์ถูกต้อง
- [ ] `preprocess_for_search` กับ Thai query return tokens
- [ ] `tokenize_thai` ตัดคำไทยได้
- [ ] `normalize_thai` แก้ typo ได้ (เเม่→แม่)

### Effort: 2-4 hours | Files: 1-2

---

## WP-2: MCP Layer Coverage — Layer 1/2/5 Tools (P0 Critical)

> **Gap**: Gap 1 จาก Gap Analysis  
> **Problem**: 3 layers ไม่มี direct MCP tools — ใช้ได้แค่ผ่าน `add_memory` auto-classification

### สิ่งที่ต้องทำ

| # | Task | File | Detail |
|---|------|------|--------|
| 2.1 | เพิ่ม Layer 1 tools (3 tools) | `graphiti_mcp_server.py` | `get_user_preferences`, `update_user_preferences`, `reset_user_preferences` |
| 2.2 | เพิ่ม Layer 2 tools (4 tools) | `graphiti_mcp_server.py` | `find_procedures`, `add_procedure`, `get_procedure`, `record_procedure_success` |
| 2.3 | เพิ่ม Layer 5 tools (4 tools) | `graphiti_mcp_server.py` | `get_working_context`, `set_working_context`, `delete_working_context`, `clear_working_session` |
| 2.4 | Wire tools → SynapseService | `synapse_service.py` | เพิ่ม methods ที่ขาดใน SynapseService |

### Implementation Detail

```python
# === Layer 1: User Model Tools ===

@mcp.tool()
async def get_user_preferences(user_id: str = "default") -> dict:
    """Get user preferences and expertise."""
    return synapse_service.get_user_context()

@mcp.tool()
async def update_user_preferences(
    user_id: str = "default",
    language: str | None = None,
    response_style: str | None = None,
    add_expertise: dict | None = None,
    add_topic: str | None = None,
    add_note: str | None = None,
) -> SuccessResponse | ErrorResponse:
    """Update user preferences, expertise, or notes."""

@mcp.tool()
async def reset_user_preferences(user_id: str = "default") -> SuccessResponse:
    """Reset user preferences to defaults."""

# === Layer 2: Procedural Tools ===

@mcp.tool()
async def find_procedures(trigger: str, limit: int = 5) -> dict:
    """Find procedures matching a trigger phrase."""

@mcp.tool()
async def add_procedure(
    trigger: str, steps: list[str],
    source: str = "explicit", topics: list[str] | None = None,
) -> SuccessResponse | ErrorResponse:
    """Add a new procedure (how-to pattern)."""

@mcp.tool()
async def get_procedure(procedure_id: str) -> dict | ErrorResponse:
    """Get a specific procedure by ID."""

@mcp.tool()
async def record_procedure_success(procedure_id: str) -> SuccessResponse | ErrorResponse:
    """Record successful use of a procedure."""

# === Layer 5: Working Memory Tools ===

@mcp.tool()
async def get_working_context(key: str) -> dict:
    """Get a value from working (session) memory."""

@mcp.tool()
async def set_working_context(key: str, value: str) -> SuccessResponse:
    """Set a value in working (session) memory."""

@mcp.tool()
async def delete_working_context(key: str) -> SuccessResponse | ErrorResponse:
    """Delete a key from working memory."""

@mcp.tool()
async def clear_working_session() -> SuccessResponse:
    """Clear all working memory for current session."""
```

### Acceptance Criteria
- [ ] `get_user_preferences` return user model data
- [ ] `update_user_preferences` update expertise/language/notes
- [ ] `find_procedures` ค้นหา procedures ด้วย trigger
- [ ] `add_procedure` สร้าง procedure ใหม่ได้
- [ ] `record_procedure_success` เพิ่ม success count
- [ ] `get_working_context` / `set_working_context` get/set ค่าได้
- [ ] `clear_working_session` ล้าง working memory ได้
- [ ] MCP `tools/list` แสดง tools ใหม่ทั้งหมด
- [ ] ทุก tool มี proper error handling

### Effort: 10-16 hours | Files: 2

---

## WP-3: Identity Model + Oracle Tools (P0 Critical)

> **Gaps**: Gap 2 (Identity) + Gap 3 (Oracle Tools) จาก Gap Analysis

### Part A: Identity Model (Gap 2)

| # | Task | File | Detail |
|---|------|------|--------|
| 3.1 | เพิ่ม `agent_id`, `chat_id` ใน UserModel | `types.py` | Optional fields ใน Pydantic model |
| 3.2 | Propagate identity ผ่าน LayerManager | `manager.py` | Pass identity context ทุก operation |
| 3.3 | Update UserContext isolation | `context.py` | Support multi-level isolation: user → agent → chat |

### Part B: Oracle-like Tools (Gap 3)

| # | Task | File | Detail |
|---|------|------|--------|
| 3.4 | Implement `synapse_consult` | `synapse_service.py` + `graphiti_mcp_server.py` | ค้นหาทุก layer แล้วสรุปคำแนะนำ |
| 3.5 | Implement `synapse_reflect` | เดียวกัน | สุ่ม insight จาก episodic + semantic |
| 3.6 | Implement `synapse_analyze` | เดียวกัน | วิเคราะห์ patterns จาก procedures + episodes |
| 3.7 | Implement `synapse_consolidate` | เดียวกัน | Promote episodic → semantic เมื่อ pattern ซ้ำ |

### Acceptance Criteria
- [ ] `UserModel` มี `agent_id`, `chat_id` fields
- [ ] Identity hierarchy: `user_id → agent_id → chat_id → session_id`
- [ ] `synapse_consult("ควรใช้ framework ไหน?")` → return คำแนะนำจาก memory
- [ ] `synapse_reflect()` → return random insight
- [ ] `synapse_analyze("my coding patterns")` → return pattern analysis
- [ ] `synapse_consolidate()` → promote repeated episodes to semantic facts

### Effort: 14-21 hours | Files: 3-4

---

## WP-4: API Completeness + Error Handling (P1 High)

> **Gaps**: Gap 4 (API) + Gap 5 (Error Handling) + Gap 7 (Integration)

### Part A: Missing API Methods (Gap 4)

| # | Task | File | Detail |
|---|------|------|--------|
| 4.1 | `reset_user_model()` | `synapse_service.py` | Delegate to UserModelManager.reset |
| 4.2 | `update_user_model(**kwargs)` | `synapse_service.py` | Full update API (not just add_note) |
| 4.3 | `record_procedure_success()` | `synapse_service.py` | Delegate to ProceduralManager |
| 4.4 | `learn_procedure()` | `synapse_service.py` | Direct procedure creation |
| 4.5 | `set_session()` / `end_session()` | `synapse_service.py` | Session lifecycle management |

### Part B: Error Handling (Gap 5)

| # | Task | File | Detail |
|---|------|------|--------|
| 4.6 | Input validation ทุก MCP tool | `graphiti_mcp_server.py` | Validate required params, types, lengths |
| 4.7 | Database error handling | `graphiti_mcp_server.py` | Catch DB errors → user-friendly messages |
| 4.8 | Graceful degradation | `graphiti_mcp_server.py` | ถ้า Graphiti down → ยังใช้ local layers ได้ |
| 4.9 | Rate limiting (basic) | `graphiti_mcp_server.py` | Simple token bucket per client |

### Part C: Integration Points (Gap 7)

| # | Task | File | Detail |
|---|------|------|--------|
| 4.10 | Connect SynapseService ↔ QueueService | `graphiti_mcp_server.py` | Sync queue สำหรับ layer operations |
| 4.11 | Connect SynapseService ↔ Qdrant | `synapse_service.py` | Vector search integration ใน search_memory |

### Acceptance Criteria
- [ ] ทุก SynapseService method มี explicit API
- [ ] Invalid input → clear error message (ไม่ crash)
- [ ] DB connection failure → graceful error response
- [ ] ถ้า Graphiti down → local layers (1,2,4,5) ยังทำงานได้
- [ ] Session lifecycle: `set_session()` → work → `end_session()`

### Effort: 20-30 hours | Files: 2-3

---

## WP-5: Working Memory Session Persistence (P1 High)

> **Gap**: Gap 6 จาก Gap Analysis  
> **Problem**: Working memory หายเมื่อ restart — ไม่ persist ข้าม sessions

### สิ่งที่ต้องทำ

| # | Task | File | Detail |
|---|------|------|--------|
| 5.1 | Add SQLite persistence | `working.py` | `_load_session()`, `_save_session()` |
| 5.2 | Session table schema | `working.py` | `working_sessions(session_id, key, value, created_at, expires_at)` |
| 5.3 | Auto-save on set/delete | `working.py` | Write-through to DB |
| 5.4 | Session restoration | `working.py` | Load ล่าสุด session เมื่อ restart |
| 5.5 | Session expiry | `working.py` | Clear sessions เก่ากว่า 24h (configurable) |
| 5.6 | Feature flag | `working.py` | `SYNAPSE_PERSIST_WORKING_MEMORY` (default: false) |

### Acceptance Criteria
- [ ] Working memory survives server restart (เมื่อ enable)
- [ ] Feature flag off → behavior เหมือนเดิม (in-memory only)
- [ ] Session expiry ทำงาน — ไม่เก็บ sessions เก่า
- [ ] Thread-safe persistence

### Effort: 10-15 hours | Files: 1

---

## WP-6: Comprehensive Test Suite (P1 High)

> **Gaps**: Gap 9 (Testing) + QA Test Plan findings  
> **Problem**: 63 tests ส่วนใหญ่ใช้ mock → ไม่ได้ทดสอบ logic จริง

### สิ่งที่ต้องเขียน

#### Part A: Unit Tests ที่ขาด (tests/test_qa_unit.py)

| # | Test Area | Tests Count | Detail |
|---|-----------|------------|--------|
| 6.1 | Decay System | 8 | `compute_decay_score()`, `should_forget()`, edge cases, boost |
| 6.2 | Episodic TTL + Archive | 8 | TTL expiry logic, `purge_expired()` archives, `restore_episode()` |
| 6.3 | Procedural FTS5 + Decay | 6 | FTS5 search Thai/English, decay scoring, refresh |
| 6.4 | Working Memory ops | 6 | `increment_counter()`, `append_to_list()`, `merge_dict()`, session |
| 6.5 | User Model persistence | 5 | Multi-user SQLite, all update variants |
| 6.6 | Thai NLP unit tests | 10 | `detect_language()`, `tokenize()`, `normalize()`, `spell_check()`, stopwords |
| 6.7 | Sync Queue | 6 | Task lifecycle, retry backoff, feature flag, stats |
| 6.8 | Data Types | 5 | Enum completeness, model creation, serialization |
| 6.9 | Qdrant Client | 4 | Hash fallback, filter building, preprocessing |
| | **Subtotal** | **~58** | |

#### Part B: Integration Tests (tests/test_qa_integration.py)

| # | Test Area | Tests Count | Detail |
|---|-----------|------------|--------|
| 6.10 | MCP Health + Init | 3 | Health endpoint, get_status, session init |
| 6.11 | MCP Memory Tools | 8 | add_memory, search_*, get_*, delete_* |
| 6.12 | MCP Thai NLP Tools | 6 | All 6 Thai tools with actual Thai text |
| 6.13 | MCP New L1/L2/L5 Tools | 8 | ทุก tool ใหม่จาก WP-2 |
| 6.14 | End-to-End Flows | 5 | Full lifecycle, layer classification, Thai content |
| | **Subtotal** | **~30** | |

### Acceptance Criteria
- [ ] Unit tests: `pytest tests/test_qa_unit.py -v` → ALL PASS (ไม่ต้อง Docker)
- [ ] Integration tests: `pytest tests/test_qa_integration.py -v` → ALL PASS (ต้อง Docker)
- [ ] Total test count ≥ 150 (63 existing + 58 unit + 30 integration)
- [ ] Coverage ≥ 80% on core modules

### Effort: 24-36 hours | Files: 2-3

---

## WP-7: Config, Docs, Security, Performance (P2-P3)

> **Gaps**: Gap 8, 10, 11, 12, 13, 14

### Part A: Configuration (Gap 8) — P2

| # | Task | File | Detail |
|---|------|------|--------|
| 7.1 | Extract hardcoded defaults | `schema.py` | Move to config.yaml |
| 7.2 | Add config validation | `schema.py` | Pydantic validators for ranges |
| 7.3 | Environment-specific configs | `config/` | `config.dev.yaml`, `config.staging.yaml` |

### Part B: Documentation (Gap 10, 14) — P2-P3

| # | Task | File | Detail |
|---|------|------|--------|
| 7.4 | API Documentation | `docs/API.md` | ทุก MCP tool — params, response, examples |
| 7.5 | Configuration Guide | `docs/CONFIG_GUIDE.md` | YAML options, env vars, provider setup |
| 7.6 | Quick Start Tutorial | `docs/TUTORIAL.md` | Step-by-step สำหรับ new users |
| 7.7 | Migration Guide | `docs/MIGRATION.md` | Upgrade instructions ระหว่าง versions |

### Part C: Performance (Gap 11) — P2

| # | Task | File | Detail |
|---|------|------|--------|
| 7.8 | Fix N+1 queries in `search_all()` | `manager.py` | Batch queries + asyncio.gather |
| 7.9 | Add caching layer | `manager.py` | LRU cache สำหรับ frequent lookups |
| 7.10 | Benchmark tests | `tests/` | Response time assertions |

### Part D: Security (Gap 12) — P3

| # | Task | File | Detail |
|---|------|------|--------|
| 7.11 | Input sanitization | `graphiti_mcp_server.py` | Length limits, special char escaping |
| 7.12 | SQL injection prevention | `episodic.py`, `procedural.py` | Verify parameterized queries |
| 7.13 | Path traversal in isolation | `context.py` | Validate user_id (no `../`) |
| 7.14 | Rate limiting | `graphiti_mcp_server.py` | Token bucket per endpoint |
| 7.15 | Auth middleware (optional) | `graphiti_mcp_server.py` | API key or JWT |

### Part E: Docker/Deployment (Gap 13) — P3

| # | Task | File | Detail |
|---|------|------|--------|
| 7.16 | Health check improvements | `docker-compose.yml` | Container health checks |
| 7.17 | Monitoring setup | `docker-compose.yml` | Prometheus metrics endpoint |
| 7.18 | Log aggregation | `Dockerfile` | Structured JSON logging |

### Acceptance Criteria
- [ ] ไม่มี hardcoded defaults ใน source code
- [ ] API docs ครบทุก MCP tool
- [ ] `search_all()` ใช้ `asyncio.gather()` แทน sequential
- [ ] ไม่มี SQL injection vulnerabilities
- [ ] user_id validation ป้องกัน path traversal
- [ ] Docker health checks ทำงาน

### Effort: 30-48 hours | Files: 8-12

---

## Execution Order (Dependency Graph)

```
Week 1: WP-1 (Thai Fix) ──────────────────────────────────────┐
         ↓                                                      │
Week 1: WP-2 (L1/L2/L5 MCP Tools) ───────────────────────────┤
         ↓                                                      │
Week 2: WP-3 (Identity + Oracle) ← depends on WP-2            │
         ↓                                                      │
Week 2: WP-4 (API + Error Handling) ← depends on WP-2         │
         ↓                                                      │
Week 2: WP-5 (Session Persistence)  ← independent             │
         ↓                                                      │
Week 3: WP-6 (Test Suite) ← depends on WP-1~5 ───────────────┘
         ↓
Week 4: WP-7 (Config, Docs, Security, Perf) ← depends on WP-1~6
```

### Parallelization Opportunities

```
Parallel Group 1 (Week 1):
  ├── WP-1: Thai Encoding Fix (2-4h)
  └── WP-2: MCP Layer Tools (10-16h)

Parallel Group 2 (Week 2):
  ├── WP-3: Identity + Oracle (14-21h)
  ├── WP-4: API + Error Handling (20-30h)  ← can start after WP-2
  └── WP-5: Session Persistence (10-15h)   ← independent

Sequential (Week 3-4):
  ├── WP-6: Test Suite (24-36h)            ← needs WP-1~5 done
  └── WP-7: Config/Docs/Security (30-48h)  ← last
```

---

## Files Impact Matrix

| File | WP-1 | WP-2 | WP-3 | WP-4 | WP-5 | WP-6 | WP-7 |
|------|:----:|:----:|:----:|:----:|:----:|:----:|:----:|
| `graphiti_mcp_server.py` | ✏️ | ✏️ | ✏️ | ✏️ | | | ✏️ |
| `thai_nlp_tools.py` | ✏️ | | | | | | |
| `synapse_service.py` | | ✏️ | ✏️ | ✏️ | | | |
| `types.py` | | | ✏️ | | | | |
| `manager.py` | | | ✏️ | | | | ✏️ |
| `context.py` | | | ✏️ | | | | ✏️ |
| `working.py` | | | | | ✏️ | | |
| `tests/test_qa_unit.py` | | | | | | 🆕 | |
| `tests/test_qa_integration.py` | | | | | | 🆕 | |
| `docs/API.md` | | | | | | | 🆕 |
| `docs/CONFIG_GUIDE.md` | | | | | | | 🆕 |
| `config/schema.py` | | | | | | | ✏️ |
| `docker-compose.yml` | | | | | | | ✏️ |

✏️ = modify existing | 🆕 = create new

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|-----------|
| WP-2 breaks existing MCP tools | High | Low | เพิ่ม tools ใหม่ ไม่แก้ tools เก่า |
| WP-3 Identity change breaks isolation | High | Medium | Backward compatible — fields Optional |
| WP-5 Session persistence slows working memory | Medium | Medium | Feature flag default off |
| WP-6 Tests flaky กับ Thai NLP | Medium | High | Use fixed Thai text, pin pythainlp version |
| WP-7 Security changes break existing clients | Low | Low | Non-breaking additions only |

---

## Verification Checklist (สำหรับ QA Sign-off)

### Phase 1: After WP-1~2

```bash
# 1. Existing tests still pass
pytest tests/ -v  # → 63/63 PASS

# 2. MCP server starts
docker-compose up -d
curl http://localhost:47780/health  # → {"status": "healthy"}

# 3. New L1/L2/L5 tools appear
curl -X POST http://localhost:47780/mcp -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
# → Should list 27+ tools (was 16)

# 4. Thai tools work
curl -X POST http://localhost:47780/mcp -d '{
  "jsonrpc":"2.0","method":"tools/call","id":1,
  "params":{"name":"tokenize_thai","arguments":{"text":"ภาษาไทยเป็นภาษาที่สวยงาม"}}
}'
# → tokens: ["ภาษา","ไทย","เป็น","ภาษา","ที่","สวย","งาม"]
```

### Phase 2: After WP-3~5

```bash
# 5. Identity model works
# 6. Oracle tools respond
# 7. Working memory persists (when enabled)
# 8. Error handling returns proper messages
```

### Phase 3: After WP-6

```bash
# 9. Full test suite
pytest tests/ -v  # → 150+ tests, ALL PASS

# 10. Coverage
pytest --cov=synapse tests/ -v  # → ≥80%
```

### Phase 4: After WP-7

```bash
# 11. Documentation complete
# 12. No security vulnerabilities
# 13. Performance benchmarks pass
# 14. Docker health checks work
```

---

## Summary Table — ทุกสิ่งที่ต้องแก้ไข

| # | สิ่งที่ต้องทำ | Priority | WP | Gap Ref | Status |
|---|-------------|----------|-----|---------|--------|
| 1 | Fix Thai encoding ใน MCP tools | P0 | WP-1 | Gap 11.5 | ❌ TODO |
| 2 | เพิ่ม MCP tools สำหรับ Layer 1 (User Model) — 3 tools | P0 | WP-2 | Gap 1 | ❌ TODO |
| 3 | เพิ่ม MCP tools สำหรับ Layer 2 (Procedural) — 4 tools | P0 | WP-2 | Gap 1 | ❌ TODO |
| 4 | เพิ่ม MCP tools สำหรับ Layer 5 (Working) — 4 tools | P0 | WP-2 | Gap 1 | ❌ TODO |
| 5 | เพิ่ม `agent_id`, `chat_id` ใน Identity Model | P0 | WP-3 | Gap 2 | ❌ TODO |
| 6 | Implement `synapse_consult` Oracle tool | P0 | WP-3 | Gap 3 | ❌ TODO |
| 7 | Implement `synapse_reflect` Oracle tool | P0 | WP-3 | Gap 3 | ❌ TODO |
| 8 | Implement `synapse_analyze` Oracle tool | P0 | WP-3 | Gap 3 | ❌ TODO |
| 9 | Implement `synapse_consolidate` Oracle tool | P0 | WP-3 | Gap 3 | ❌ TODO |
| 10 | เพิ่ม missing methods ใน SynapseService API | P1 | WP-4 | Gap 4 | ❌ TODO |
| 11 | Input validation ทุก MCP tool | P1 | WP-4 | Gap 5 | ❌ TODO |
| 12 | Database error handling + graceful degradation | P1 | WP-4 | Gap 5 | ❌ TODO |
| 13 | SynapseService ↔ QueueService integration | P1 | WP-4 | Gap 7 | ❌ TODO |
| 14 | Working Memory session persistence | P1 | WP-5 | Gap 6 | ❌ TODO |
| 15 | Unit tests: Decay system (8 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 16 | Unit tests: Episodic TTL + Archive (8 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 17 | Unit tests: Procedural FTS5 + Decay (6 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 18 | Unit tests: Thai NLP (10 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 19 | Unit tests: Sync Queue (6 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 20 | Unit tests: Working Memory ops (6 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 21 | Unit tests: User Model persistence (5 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 22 | Unit tests: Data Types + Qdrant (9 tests) | P1 | WP-6 | QA finding | ❌ TODO |
| 23 | Integration tests: MCP tools (30 tests) | P1 | WP-6 | Gap 9 | ❌ TODO |
| 24 | Configuration — extract hardcoded defaults | P2 | WP-7 | Gap 8 | ❌ TODO |
| 25 | API Documentation | P2 | WP-7 | Gap 10 | ❌ TODO |
| 26 | Fix N+1 queries ใน `search_all()` | P2 | WP-7 | Gap 11 | ❌ TODO |
| 27 | SQL injection verification | P3 | WP-7 | Gap 12 | ❌ TODO |
| 28 | Path traversal prevention ใน user isolation | P3 | WP-7 | Gap 12 | ❌ TODO |
| 29 | Docker health checks + monitoring | P3 | WP-7 | Gap 13 | ❌ TODO |
| 30 | Tutorials + Migration Guide | P3 | WP-7 | Gap 14 | ❌ TODO |

**Total: 30 items | Est. 110-170 hours | 13-18 files affected**

---

*Plan compiled from: Gap Analysis Report, MCP Tools Test Report, QA Test Plan, and full codebase audit.*
