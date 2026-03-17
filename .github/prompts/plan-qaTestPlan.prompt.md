# QA Test Plan: Synapse AI Memory System — Comprehensive Verification

## สรุป (TL;DR)

โปรเจค Synapse อ้างว่า **"ALL PHASES CERTIFIED — 63/63 tests passing (100%)"** แต่จากการวิเคราะห์โค้ดเทสที่มีอยู่พบปัญหาสำคัญ:

| ข้อค้นพบ | รายละเอียด |
|---|---|
| **เทสส่วนใหญ่ใช้ mock** | SynapseService, Semantic layer เทสกับ `MagicMock`/`AsyncMock` — ไม่ได้ทดสอบ logic จริง |
| **MCP Tools test แยกจาก suite** | `test_all_mcp_tools.py` ต้องรัน live server ด้วยมือ ไม่อยู่ใน `pytest` |
| **Features ไม่มี test coverage** | Decay computation, Archive, Sync Queue, NLP unit tests, Episodic TTL, Procedural FTS5 |
| **Gap ที่ยอมรับแล้ว** | MCP ไม่ expose Layer 1 (UserModel), Layer 2 (Procedural), Layer 5 (Working) CRUD |

---

## Phase 1: Unit Tests — Logic & Data Layer (ไม่ต้อง Docker)

### Step 1.1: Layer 1 — User Model (`UserModelManager`)
**File to test**: `synapse/layers/user_model.py`
- `get_user_model()` — default values ถูกต้อง
- `update_user_model()` — language, response_style, timezone
- `add_expertise`, `add_topic`, `add_note`
- **SQLite persistence** — ข้อมูลบันทึกจริง (ใช้ temp dir)
- **Multi-user** — แยก user data ได้

### Step 1.2: Layer 2 — Procedural Memory (`ProceduralManager`)
**File to test**: `synapse/layers/procedural.py`
- `learn_procedure()`, `find_procedure()`, `record_success()`
- **FTS5 full-text search** — Thai + English
- **Decay scoring** — λ=0.005, half-life ≈139 days
- `refresh_decay_scores()`, SQLite persistence

### Step 1.3: Layer 3 — Semantic Memory (`SemanticManager`)
**File to test**: `synapse/layers/semantic.py`
- `add_entity()`, `add_fact()`, `get_entity()`, `update_entity()`
- `supersede_fact()` — temporal metadata (valid_at/invalid_at)
- `search()`, `get_related_entities()`, `cleanup_forgotten()`

### Step 1.4: Layer 4 — Episodic Memory (`EpisodicManager`)
**File to test**: `synapse/layers/episodic.py`
- `record_episode()`, `find_episodes()`
- **TTL expiry** — 90-day default
- **Archive before purge** — `purge_expired()` ไม่ลบจริง (archive)
- `extend_ttl()`, `get_episode_stats()`, FTS5 search

### Step 1.5: Layer 5 — Working Memory (`WorkingManager`)
**File to test**: `synapse/layers/working.py`
- `set_context()` / `get_context()` / `clear_context()`
- `get_all_context()`, `get_context_stats()`
- **In-memory only** — ไม่มี persistence

### Step 1.6: Decay System
**File to test**: `synapse/layers/decay.py`
- `compute_decay_score()` — e^(-λt) คำนวณถูกต้อง
- `should_forget()` — threshold logic
- `DecayConfig` constants: `LAMBDA_DEFAULT=0.01`, `LAMBDA_PROCEDURAL=0.005`, `TTL_EPISODIC_DAYS=90`
- **Edge cases** — score ∈ [0.0, 1.0], boost on access

### Step 1.7: Layer Classifier
**File to test**: `synapse/classifiers/layer_classifier.py`
- **Keyword classification** (Thai + English per layer × 5 layers)
  - USER_MODEL: "ฉันชอบ", "I prefer", "favorite"
  - PROCEDURAL: "วิธีทำ", "How to", "steps"
  - EPISODIC: "เมื่อวาน", "yesterday", "last week"
  - WORKING: "current task", "right now"
  - SEMANTIC: default fallback (facts/knowledge)
- **Context hints** — `temporary→WORKING`, `user_preference→USER_MODEL`
- **LLM classification** — mock LLM → correct layer parse
- **LLM fallback** — error → keyword fallback
- **Feature flag** — `SYNAPSE_USE_LLM_CLASSIFICATION`

### Step 1.8: Thai NLP (*ยังไม่มี unit tests เลย*)
**Files to test**: `synapse/nlp/thai.py`, `synapse/nlp/preprocess.py`, `synapse/nlp/router.py`
- `detect_language()` — Thai/English/Mixed
- `tokenize()` — newmm word segmentation
- `normalize()` — typo fix (เเ→แ), zero-width removal
- `spell_check()`, `remove_stopwords()`
- `preprocess_for_extraction()`, `preprocess_for_search()`
- **English fallback** — graceful handling

### Step 1.9: SynapseService Bridge
**File to test**: `synapse/services/synapse_service.py`
- Full flow: classify → route → store
- All operations: `add_memory`, `search_memory`, `add_entity`, `get_entity`, `get_episodes`, `find_procedure`, `get_user_context`, `health_check`, working context ops

### Step 1.10: LayerManager Cross-Layer
**File to test**: `synapse/layers/manager.py`
- `search_all()` — ค้นหาทุก 5 layers
- `detect_layer()` / `detect_layer_async()`
- `run_maintenance()`, `get_memory_stats()`, `create_context_for_prompt()`

### Step 1.11: User Isolation
**Files to test**: `synapse/layers/context.py`, `synapse/layers/manager.py`
- `UserContext.create()`, lazy loading managers
- Feature flag: `SYNAPSE_USE_USER_ISOLATION`
- Data separation between users

### Step 1.12: Sync Queue (*ยังไม่มี tests*)
**File to test**: `synapse/services/sync_queue.py`
- `SyncQueue`, `SyncTask`, status transitions
- Retry with exponential backoff
- Feature flag: `SYNAPSE_USE_SYNC_QUEUE`

### Step 1.13: Data Types & Models
**File to test**: `synapse/layers/types.py`
- `MemoryLayer` (5 values), `EntityType`, `RelationType` enums
- `SynapseNode`, `SynapseEdge`, `SynapseEpisode`, `ProceduralMemory`, `UserModel`, `SearchResult`

---

## Phase 2: Integration Tests (ต้อง `docker-compose up`)

### Step 2.1: MCP Server Health
- Docker Compose startup สำเร็จ
- `/health` → `{"status": "healthy"}`
- `get_status` → database connected

### Step 2.2: MCP Tools — Memory (11 tools)
- `add_memory` (text/JSON/message) → queue + process
- `search_nodes`, `search_memory_facts`, `search_memory_layers`
- `get_episodes`, `delete_episode`
- `get_entity_edge`, `delete_entity_edge`
- `clear_graph`

### Step 2.3: MCP Tools — Thai NLP (6 tools)
- `detect_language`, `preprocess_for_extraction`, `preprocess_for_search`
- `tokenize_thai`, `normalize_thai`, `is_thai_text`

### Step 2.4: End-to-End Flows
- Full memory lifecycle: add → search → retrieve → delete
- Layer classification: procedural content → PROCEDURAL layer
- Thai content: detect → tokenize → store → search
- Fact supersession: add → contradict → verify old invalidated
- Concurrent episodes: multiple `add_memory` → all processed

### Step 2.5: Configuration
- YAML config loading, env var expansion
- `LLMClientFactory`, `EmbedderFactory`, `DatabaseDriverFactory`

---

## Phase 3: Gap Analysis — ช่องโหว่ที่ค้นพบ

| # | Gap | ระดับ | รายละเอียด |
|---|-----|-------|-----------|
| 1 | MCP ไม่ expose User Model CRUD | High | `get_user_model`, `update_user_model` ไม่มีใน MCP tools |
| 2 | MCP ไม่ expose Procedural CRUD | High | `search_procedures`, `add_procedure` ไม่มีใน MCP tools |
| 3 | MCP ไม่ expose Working Memory | High | `get_context`, `set_context`, `clear_context` ไม่มีใน MCP tools |
| 4 | Decay — ไม่มี test จริง | Medium | ไม่มี test ที่ verify e^(-λt) computation |
| 5 | Archive — ไม่มี test | Medium | `purge_expired()` อ้างว่า archive แต่ไม่มี test verify |
| 6 | Sync Queue — ไม่มี test | Medium | `SyncQueue` ไม่มี test เลย |
| 7 | Thai NLP — ไม่มี unit test | Medium | เทสเฉพาะผ่าน MCP HTTP, ไม่มี direct unit test |
| 8 | Episodic TTL — ไม่มี test | Medium | TTL 90 days logic ไม่ได้ถูก test |
| 9 | Procedural FTS5 — partial test | Low | มีเทส FTS5 ของ episodic แต่ไม่มีของ procedural |
| 10 | Qdrant hash fallback — ไม่ test logic | Low | `_hash_embedding` test ไม่ verify vector quality |
| 11 | Error handling — incomplete | Low | MCP server graceful degradation ไม่ถูก test |
| 12 | No identity granularity | Info | มีแค่ `user_id`, ไม่มี agent_id/chat_id/thread_id |

---

## Verification Strategy

### Unit Tests (Phase 1)
```bash
pytest tests/test_qa_unit.py -v
# ไม่ต้องการ Docker, internet, หรือ API keys
# ใช้ temp directories สำหรับ SQLite
# ใช้ mock เฉพาะ Graphiti/Qdrant (external services)
```

### Integration Tests (Phase 2)
```bash
docker-compose up -d
pytest tests/test_qa_integration.py -v
# หรือ
python test_all_mcp_tools.py
```

### Coverage
```bash
pytest --cov=synapse tests/ -v
# เป้าหมาย: ≥80% line coverage
```

---

## Decisions

1. **Unit tests ใช้ real SQLite (temp dir)** แทน mock — เพื่อทดสอบ SQL logic จริง
2. **Semantic layer unit tests ยังใช้ mock Graphiti/Qdrant** — external services
3. **Report bilingual** — ทั้งไทยและอังกฤษ

## Further Considerations

1. **Performance benchmarks** — ยังไม่มี benchmark; ควรเพิ่มหลัง functional tests ผ่าน
2. **Security tests** — SQL injection, path traversal ใน user isolation ยังไม่มี
3. **Concurrent access** — multi-user concurrent access ที่ layer level ยังไม่ถูก test (มีแค่ MCP stress test)
