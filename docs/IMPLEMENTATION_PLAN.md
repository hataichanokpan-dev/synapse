# Synapse Implementation Plan

**Version:** 1.0
**Created:** 2026-03-13
**Status:** Approved

---

## Overview

Synapse = Graphiti (fork) + Oracle-v2 (features)

**Strategy:** Fork Graphiti, inject Oracle-v2 features

**Timeline:** 5 days

---

## Phase Overview

```
Phase 1          Phase 2          Phase 3          Phase 4          Phase 5
SETUP            GRAPH            LAYERS           NLP              DEPLOY
(Day 1)          (Day 2)          (Day 3)          (Day 4)          (Day 5)

┌─────┐          ┌─────┐          ┌─────┐          ┌─────┐          ┌─────┐
│ 🏗️  │    →     │ 🔗  │    →     │ 📚  │    →     │ 🇹🇭  │    →     │ 🚀  │
└─────┘          └─────┘          └─────┘          └─────┘          └─────┘

Done: 50%        Done: 0%         Done: 0%         Done: 0%         Done: 0%
```

---

## Phase 1: SETUP (Day 1)

### Goal

> มีโครงสร้างโปรเจคพร้อม + Graphiti ทำงานได้ + FalkorDB running

### Current Status: 50%

| Task | Status |
|------|--------|
| สร้างโฟลเดอร์โปรเจค | ✅ Done |
| Git init | ✅ Done |
| pyproject.toml | ✅ Done |
| README.md | ✅ Done |
| docs/ (3 files) | ✅ Done |
| synapse/layers/types.py | ✅ Done |
| synapse/layers/decay.py | ✅ Done |
| Empty folders | ✅ Done |
| **Fork Graphiti** | ❌ Missing |
| **Setup FalkorDB** | ❌ Missing |
| **Test Graphiti MCP** | ❌ Missing |

### Tasks

#### Task 1.1: Fork Graphiti

**Goal:** มี Graphiti code ในโปรเจค

**Steps:**
1. `git clone https://github.com/getzep/graphiti temp_graphiti`
2. Copy ไฟล์ที่ต้องใช้:
   - `graphiti_core/` → `synapse/graphiti/`
   - `mcp_server/` → `synapse/mcp_server/`
3. `rm -rf temp_graphiti`
4. Update imports ใน `pyproject.toml`

**Deliverables:**
- `synapse/graphiti/` (core engine)
- `synapse/mcp_server/` (MCP server)

**Verification:**
- [ ] `graphiti/` folder exists
- [ ] `mcp_server/` folder exists

#### Task 1.2: Setup FalkorDB

**Goal:** FalkorDB running ใน Docker

**Steps:**
1. Create `docker-compose.yml`
2. `docker compose up -d falkordb`
3. Test: `redis-cli -p 6379 PING`

**Deliverables:**
- `docker-compose.yml`
- FalkorDB container running on port 6379

**Verification:**
- [ ] `docker ps` shows falkordb
- [ ] `redis-cli PING` returns PONG

#### Task 1.3: Install Dependencies

**Goal:** ทุก dependency ติดตั้งพร้อม

**Steps:**
1. `pip install -e ".[dev]"`
2. `pip install graphiti-core`
3. Verify: `python -c "import graphiti; print('OK')"`

**Deliverables:**
- All dependencies installed
- Virtual environment ready

**Verification:**
- [ ] `import graphiti` works
- [ ] `import synapse` works

#### Task 1.4: Test Graphiti MCP

**Goal:** Graphiti MCP server ทำงานได้

**Steps:**
1. `cd synapse/mcp_server`
2. `python -m graphiti_mcp_server`
3. Test with MCP client

**Deliverables:**
- MCP server running on port 8000
- Basic tools working

**Verification:**
- [ ] Server starts without error
- [ ] Can call `add_episode` tool
- [ ] Can call `search` tool

### Phase 1 Exit Criteria

- ✅ Graphiti code ใน `synapse/`
- ✅ FalkorDB running
- ✅ `pip install` สำเร็จ
- ✅ MCP server ทำงานได้

---

## Phase 2: GRAPH (Day 2)

### Goal

> เชื่อม Synapse layers เข้ากับ Graphiti graph engine

### Tasks

#### Task 2.1: Understand Graphiti Architecture

**Goal:** เข้าใจโครงสร้าง Graphiti ก่อนแกะ

**Read:**
- `graphiti_core/graphiti.py` (main engine)
- `graphiti_core/extract/` (entity extraction)
- `graphiti_core/search/` (hybrid search)
- `mcp_server/` (MCP implementation)

**Output:**
- `docs/GRAPHITI_NOTES.md` (สรุปที่เข้าใจ)

#### Task 2.2: Create Storage Clients

**Goal:** สร้าง client สำหรับ FalkorDB + Qdrant

**Files to create:**
- `synapse/storage/falkordb.py`
- `synapse/storage/qdrant_client.py`
- `synapse/storage/sqlite.py`

**Functions:**
- `FalkorDBClient`: connect, query, close
- `QdrantClient`: connect, add, search, delete
- `SQLiteClient`: connect, execute, close

#### Task 2.3: Integrate Memory Layers with Graph

**Goal:** เพิ่ม `memory_layer` property ให้ graph nodes

**Modify:**
- `graphiti_core/entities.py` → add `memory_layer` field
- `graphiti_core/edges.py` → add `decay_score` field

**New:**
- `synapse/layers/classifier.py` → auto layer detection

**Logic:**
```
User preference → user_model layer
"How to" pattern → procedural layer
Fact/principle → semantic layer
Conversation → episodic layer
```

#### Task 2.4: Add Temporal Properties

**Goal:** ทุก edge มี `valid_at` / `invalid_at`

Already in Graphiti! ✅
- Just verify it works
- Add helper functions if needed

### Phase 2 Deliverables

| File | Description |
|------|-------------|
| `docs/GRAPHITI_NOTES.md` | Architecture notes |
| `synapse/storage/falkordb.py` | Graph DB client |
| `synapse/storage/qdrant_client.py` | Vector DB client |
| `synapse/layers/classifier.py` | Layer auto-detection |
| Modified graphiti files | + memory_layer field |

### Phase 2 Exit Criteria

- ✅ เข้าใจ Graphiti architecture
- ✅ Storage clients ทำงานได้
- ✅ Nodes มี `memory_layer` property
- ✅ Temporal properties ทำงาน

---

## Phase 3: LAYERS (Day 3)

### Goal

> Five-Layer Memory System ทำงานครบ พร้อม decay scoring

### Tasks

#### Task 3.1: Implement Layer 1 (User Model)

**Goal:** เก็บ preferences + expertise

**Files:**
- `synapse/layers/user_model.py`

**Functions:**
- `get_user_model(user_id)` → UserModel
- `update_user_model(user_id, partial)` → UserModel
- `reset_user_model(user_id)`

**Storage:**
- SQLite (private, encrypted optional)
- Graph: `(User)` node with properties

**Behavior:**
- Never decay (`decay_score = 1.0` ตลอด)
- Inject into every system prompt

#### Task 3.2: Implement Layer 2 (Procedural)

**Goal:** เก็บ "วิธีทำงาน" patterns

**Files:**
- `synapse/layers/procedural.py`

**Functions:**
- `find_procedure(trigger)` → List[ProceduralMemory]
- `learn_procedure(trigger, steps, source)`
- `record_success(procedure_id)`

**Storage:**
- Graph: `(Procedure)` nodes with trigger edges
- Vector: Qdrant for semantic search

**Behavior:**
- Slow decay (λ = 0.005, half-life ~139 days)
- Success count boosts `decay_score`

#### Task 3.3: Implement Layer 3 (Semantic)

**Goal:** เก็บ principles + patterns + learnings

Already in Graphiti! ✅
- Entity nodes + Fact edges
- Hybrid search

**Add:**
- Decay scoring on retrieval
- Supersede pattern (mark old as outdated)

#### Task 3.4: Implement Layer 4 (Episodic)

**Goal:** เก็บ conversation summaries with TTL

**Files:**
- `synapse/layers/episodic.py`

**Functions:**
- `record_episode(summary, topics, outcome)`
- `find_episodes(topic, limit)`
- `purge_expired()`

**Storage:**
- Graph: `(Episode)` nodes with `expires_at`
- Vector: Qdrant for semantic search

**Behavior:**
- TTL: 90 days
- Extend +30 days on access
- Archive before delete (compact summary)

#### Task 3.5: Implement Layer 5 (Working)

**Goal:** Session context (temporary)

**Files:**
- `synapse/layers/working.py`

**Functions:**
- `set_context(key, value)`
- `get_context(key)`
- `clear_context()`

**Storage:**
- In-memory only (dict)
- No persistence

**Behavior:**
- Cleared on session end
- No decay (binary alive/dead)

### Phase 3 Deliverables

| Layer | File | Key Functions |
|-------|------|---------------|
| 1. User Model | `user_model.py` | get, update, reset |
| 2. Procedural | `procedural.py` | find, learn, record |
| 3. Semantic | (Graphiti) | search, add, supersede |
| 4. Episodic | `episodic.py` | record, find, purge |
| 5. Working | `working.py` | set, get, clear |

### Phase 3 Exit Criteria

- ✅ All 5 layers implemented
- ✅ Decay scoring works
- ✅ TTL for episodic works
- ✅ User model injects to prompt

---

## Phase 4: NLP (Day 4)

### Goal

> Thai NLP sidecar ทำงาน + integrate กับ Synapse

### Tasks

#### Task 4.1: Create Thai NLP Client

**Goal:** Client สำหรับเรียก Thai NLP service

**Files:**
- `synapse/nlp/thai.py`
- `synapse/nlp/detector.py`

**Functions:**
- `detect_thai(text)` → bool
- `normalize(text)` → str
- `tokenize(text)` → List[str]
- `spellcheck(text)` → str

**Integration:**
- HTTP client to thai-nlp-sidecar
- Or embed pythainlp directly

#### Task 4.2: Integrate with Entity Extraction

**Goal:** Thai text → better entity extraction

**Modify:**
- `graphiti_core/extract/extract_nodes_edges.py`

**Logic:**
```python
if detect_thai(text):
    text = thai_nlp.normalize(text)
    text = thai_nlp.tokenize(text)
# Then run Graphiti's LLM extraction
```

#### Task 4.3: Integrate with Search

**Goal:** Thai query → better search results

**Modify:**
- `graphiti_core/search/` (search functions)

**Logic:**
```python
if detect_thai(query):
    query = thai_nlp.normalize(query)
    tokens = thai_nlp.tokenize(query)
# Use tokens for FTS5 search
```

#### Task 4.4: Add Thai NLP to MCP Tools

**Goal:** MCP tools ใช้ Thai NLP อัตโนมัติ

**Modify:**
- `synapse/mcp/tools.py`

**Logic:**
- `synapse_remember`: preprocess with Thai NLP
- `synapse_recall`: preprocess query with Thai NLP

### Phase 4 Deliverables

| File | Description |
|------|-------------|
| `synapse/nlp/thai.py` | Thai NLP client |
| `synapse/nlp/detector.py` | Thai detection |
| Modified extract | Thai entity extraction |
| Modified search | Thai search |

### Phase 4 Exit Criteria

- ✅ Thai NLP client works
- ✅ Entity extraction handles Thai
- ✅ Search handles Thai
- ✅ MCP tools use Thai NLP

---

## Phase 5: DEPLOY (Day 5)

### Goal

> Synapse MCP server running + integrated with JellyCore

### Tasks

#### Task 5.1: Create Unified MCP Server

**Goal:** MCP server เดียวที่มีทุก tools

**Files:**
- `synapse/mcp/server.py`
- `synapse/mcp/tools.py`

**Tools:**

| Category | Tool | Description |
|----------|------|-------------|
| MEMORY | `synapse_remember` | Add with layer detection |
| | `synapse_recall` | Hybrid search |
| | `synapse_forget` | Decay/archive/delete |
| | `synapse_context` | Get user context |
| GRAPH | `synapse_query` | Graph traversal |
| | `synapse_timeline` | Temporal query |
| | `synapse_entities` | List entities |
| | `synapse_relations` | List relations |
| USER | `synapse_profile` | User model CRUD |
| SYSTEM | `synapse_stats` | Database stats |
| | `synapse_health` | Health check |
| | `synapse_backup` | Manual backup |

#### Task 5.2: Create Docker Compose

**Goal:** One-command setup

**File:**
- `docker-compose.yml`

**Services:**
- `synapse` (MCP server)
- `falkordb` (graph database)
- `qdrant` (vector database)
- `thai-nlp` (optional sidecar)

#### Task 5.3: Integrate with JellyCore

**Goal:** JellyCore ใช้ Synapse เป็นสมอง

**Modify:**
- `jellycore/.mcp.json`

```json
{
  "mcpServers": {
    "synapse": {
      "url": "http://localhost:47780/mcp"
    }
  }
}
```

#### Task 5.4: Migrate Data from Oracle-v2

**Goal:** ข้อมูลเก่าไม่หาย

**Script:**
- `scripts/migrate_oracle_v2.py`

**Steps:**
1. Export from SQLite (oracle-v2)
2. Transform to Synapse format
3. Import via `synapse_remember`
4. Verify counts match

#### Task 5.5: Testing & Documentation

**Goal:** มั่นใจว่าทำงาน

**Tests:**
- `tests/test_layers.py`
- `tests/test_nlp.py`
- `tests/test_mcp.py`
- `tests/integration/test_full.py`

**Docs:**
- Update README.md
- Add usage examples

### Phase 5 Deliverables

| File/Item | Description |
|-----------|-------------|
| `synapse/mcp/server.py` | Unified MCP server |
| `synapse/mcp/tools.py` | All MCP tools |
| `docker-compose.yml` | Full stack |
| Migration script | Oracle-v2 → Synapse |
| Tests | Unit + Integration |
| Updated docs | README + examples |

### Phase 5 Exit Criteria

- ✅ MCP server runs on port 47780
- ✅ All tools working
- ✅ `docker compose up` = ready
- ✅ JellyCore connected
- ✅ Data migrated
- ✅ Tests passing

---

## Master Checklist

```
Phase 1: SETUP (Day 1)
├── [ ] 1.1 Fork Graphiti
├── [ ] 1.2 Setup FalkorDB
├── [ ] 1.3 Install Deps
└── [ ] 1.4 Test MCP

Phase 2: GRAPH (Day 2)
├── [ ] 2.1 Understand Graphiti
├── [ ] 2.2 Storage Clients
├── [ ] 2.3 Integrate Layers
└── [ ] 2.4 Temporal Properties

Phase 3: LAYERS (Day 3)
├── [ ] 3.1 Layer 1: User Model
├── [ ] 3.2 Layer 2: Procedural
├── [ ] 3.3 Layer 3: Semantic
├── [ ] 3.4 Layer 4: Episodic
└── [ ] 3.5 Layer 5: Working

Phase 4: NLP (Day 4)
├── [ ] 4.1 Thai NLP Client
├── [ ] 4.2 Entity Extraction
├── [ ] 4.3 Search Integration
└── [ ] 4.4 MCP Integration

Phase 5: DEPLOY (Day 5)
├── [ ] 5.1 Unified MCP Server
├── [ ] 5.2 Docker Compose
├── [ ] 5.3 JellyCore Integration
├── [ ] 5.4 Data Migration
└── [ ] 5.5 Testing & Docs
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Graphiti API changes | Pin version, test updates |
| FalkorDB issues | Can switch to Neo4j |
| Thai NLP accuracy | Fine-tune as needed |
| Data migration | Test with sample first |
| MCP compatibility | Test multiple clients |

---

## References

- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Graphiti Paper](https://arxiv.org/abs/2501.13956)
- [FalkorDB Docs](https://docs.falkordb.com/)
- [MCP Protocol](https://modelcontextprotocol.io/)

---

**Last Updated:** 2026-03-13
