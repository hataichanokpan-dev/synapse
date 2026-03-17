# Synapse Backend API — Full Plan

> **Architecture:** REST API Gateway ที่เป็น bridge ระหว่าง Frontend กับ MCP Server + Direct DB access
> **ปรัชญา:** MCP tools ใช้ได้ → proxy ผ่าน / MCP tools ไม่มี → เข้า DB ตรง

---

## 0. Gap Analysis — API Spec ของคุณ vs สิ่งที่ MCP Server รองรับจริง

### สรุปจาก deep-dive: MCP Server มี 25 tools แต่ coverage แค่ ~40%

คุณออกแบบ 39 endpoints — ซึ่ง **เป็นการออกแบบที่ถูกต้อง** สำหรับ frontend ที่ครบมือ
ปัญหาคือ MCP Server ปัจจุบันไม่ได้ support ทุก operation

### Coverage Map — API Spec ↔ MCP Tool

```
┌─────────────────────────────────────┬────────┬─────────────────────────────────┐
│ Your API Endpoint                   │ Status │ MCP Tool / Gap                  │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ GET    /api/memory                  │ ❌ GAP │ ไม่มี list all memories         │
│ GET    /api/memory/:id              │ ❌ GAP │ ไม่มี get memory by UUID        │
│ POST   /api/memory                  │ ✅     │ add_memory                      │
│ PUT    /api/memory/:id              │ ❌ GAP │ ไม่มี update memory             │
│ DELETE /api/memory/:id              │ ⚠️ บาง │ delete_episode / delete_entity_edge │
│ POST   /api/memory/search           │ ✅     │ search_memory_layers            │
│ POST   /api/memory/consolidate      │ ✅     │ synapse_consolidate             │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ GET    /api/graph/nodes             │ ⚠️ บาง │ search_nodes (ต้องมี query)     │
│ GET    /api/graph/nodes/:id         │ ❌ GAP │ ไม่มี get node by UUID          │
│ GET    /api/graph/nodes/:id/edges   │ ❌ GAP │ ไม่มี neighborhood query        │
│ GET    /api/graph/edges             │ ❌ GAP │ ไม่มี list edges                │
│ GET    /api/graph/edges/:id         │ ✅     │ get_entity_edge                 │
│ DELETE /api/graph/nodes/:id         │ ❌ GAP │ ไม่มี delete node               │
│ DELETE /api/graph/edges/:id         │ ✅     │ delete_entity_edge              │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ GET    /api/episodes                │ ✅     │ get_episodes (by group_id)      │
│ GET    /api/episodes/:id            │ ❌ GAP │ ไม่มี get episode by UUID       │
│ DELETE /api/episodes/:id            │ ✅     │ delete_episode                  │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ GET    /api/procedures              │ ⚠️ บาง │ find_procedures (ต้องมี trigger)│
│ GET    /api/procedures/:id          │ ❌ GAP │ ไม่มี get by ID                 │
│ POST   /api/procedures              │ ✅     │ add_procedure                   │
│ PUT    /api/procedures/:id          │ ❌ GAP │ ไม่มี update procedure          │
│ DELETE /api/procedures/:id          │ ❌ GAP │ ไม่มี delete procedure          │
│ POST   /api/procedures/:id/success  │ ✅     │ record_procedure_success        │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ GET    /api/identity                │ ✅     │ get_identity                    │
│ PUT    /api/identity                │ ✅     │ set_identity                    │
│ DELETE /api/identity                │ ✅     │ clear_identity                  │
│ GET    /api/identity/preferences    │ ✅     │ get_user_preferences            │
│ PUT    /api/identity/preferences    │ ✅     │ update_user_preferences         │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ POST   /api/oracle/consult          │ ✅     │ synapse_consult                 │
│ POST   /api/oracle/reflect          │ ✅     │ synapse_reflect                 │
│ POST   /api/oracle/analyze          │ ✅     │ synapse_analyze                 │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ GET    /api/system/status           │ ✅     │ get_status                      │
│ GET    /api/system/stats            │ ❌ GAP │ ไม่มี stats endpoint            │
│ POST   /api/system/maintenance      │ ❌ GAP │ ไม่มี maintenance trigger       │
│ DELETE /api/system/graph            │ ✅     │ clear_graph                     │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ GET    /api/feed                    │ ❌ GAP │ ไม่มี event history             │
│ GET    /api/feed/stream             │ ❌ GAP │ ไม่มี SSE / event stream       │
├─────────────────────────────────────┼────────┼─────────────────────────────────┤
│ POST   /api/search                  │ ✅     │ search_memory_layers            │
│ POST   /api/search/graph            │ ✅     │ search_nodes + search_memory_facts │
│ POST   /api/search/vector           │ ❌ GAP │ ไม่มี direct vector search     │
└─────────────────────────────────────┴────────┴─────────────────────────────────┘
```

### Score

```
✅ MCP รองรับเต็ม:     17 / 39  (44%)
⚠️ MCP รองรับบางส่วน:    4 / 39  (10%)
❌ ต้องทำเอง (GAP):     18 / 39  (46%)
```

---

## 1. สถาปัตยกรรม — Dual-Path Architecture

### ปัญหา: MCP Server ออกแบบมาสำหรับ AI Agent ไม่ใช่ Frontend

MCP Server ใช้ JSON-RPC protocol (tools/call) ไม่ใช่ REST —
และ tools ออกแบบมาสำหรับ "ถาม-ตอบ" ไม่ใช่ "Browse & Manage"

### ทางออก: 2 แนวทาง (เลือก 1)

```
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│  Option A: Next.js API Routes (Thin Proxy + Direct DB)               │
│  ──────────────────────────────────────────────────────               │
│                                                                       │
│  Browser ──→ Next.js Route Handler ──┬──→ MCP Server (HTTP)          │
│                                      │    (17 endpoints ที่ MCP รองรับ)│
│                                      │                                │
│                                      └──→ Database Direct             │
│                                           (18 endpoints ที่ต้อง GAP)  │
│                                           ├ FalkorDB (Cypher queries) │
│                                           ├ SQLite (direct read)      │
│                                           └ Qdrant (vector search)    │
│                                                                       │
│  ✅ ข้อดี: ไม่ต้องสร้าง backend ใหม่ ใช้ Next.js ที่มีอยู่แล้ว       │
│  ❌ ข้อเสีย: Next.js route handlers ทำ DB access = coupling สูง      │
│             SQLite อยู่บน disk ของ Synapse container ไม่ใช่ Next.js   │
│             ต้อง share volume หรือ network access                     │
│                                                                       │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Option B: Python FastAPI Gateway (แนะนำ ✅)                         │
│  ──────────────────────────────────────────────────────               │
│                                                                       │
│  Browser ──→ FastAPI Gateway ──┬──→ MCP Server (internal)            │
│              (REST API)        │    (reuse SynapseService directly)   │
│                                │                                      │
│                                └──→ Database Direct                   │
│                                     ├ FalkorDB (same driver)          │
│                                     ├ SQLite (same path)              │
│                                     └ Qdrant (same client)            │
│                                                                       │
│  ✅ ข้อดี: อยู่ใน Python ecosystem เดียวกัน                          │
│           import SynapseService ตรงได้เลย ไม่ต้อง HTTP hop           │
│           Access SQLite, FalkorDB, Qdrant ด้วย driver เดิม           │
│           ไม่ต้อง duplicate logic — reuse LayerManager ทั้งหมด        │
│           Run ใน container เดียวกับ Synapse ได้                       │
│  ❌ ข้อเสีย: เพิ่ม service อีก 1 ตัว (แต่ถ้า co-locate ก็ไม่เพิ่ม)   │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### คำตอบ: **Option B — Python FastAPI Gateway**

เหตุผล:
1. **Synapse ทั้ง stack เป็น Python** — SynapseService, LayerManager, Graphiti ทุกอย่าง import ได้
2. **18 GAP endpoints ต้อง access DB ตรง** — SQLite อยู่บน disk เดียวกัน, FalkorDB ใช้ driver เดิม
3. **ไม่ต้อง rewrite business logic** — เรียก `service.find_procedure()` ได้เลย ไม่ต้อง HTTP proxy
4. **SSE/WebSocket native** — FastAPI มี `StreamingResponse` สำหรับ Feed stream
5. **Co-locate ได้** — Run ใน process เดียวกับ MCP Server หรือ container เดียวกัน
6. **Type safety** — Pydantic models ที่ Synapse ใช้อยู่แล้ว → response schema ฟรี

---

## 2. Tech Stack — Backend API

| Layer | Choice | Why |
|-------|--------|-----|
| **Language** | **Python 3.12+** | เดียวกับ Synapse. Import ตรง. ไม่ต้อง bridge. |
| **Framework** | **FastAPI 0.115+** | Async native. Auto OpenAPI docs. Pydantic integration. |
| **Server** | **Uvicorn** | ASGI. ใช้อยู่แล้วใน MCP server stack. |
| **Validation** | **Pydantic v2** | ใช้อยู่แล้วทั้ง project. Zero learning curve. |
| **Auth** | **API Key header** | Single-user system. ไม่ต้อง OAuth. `X-API-Key` header. |
| **CORS** | **FastAPI CORSMiddleware** | Allow Next.js origin. |
| **SSE** | **sse-starlette** | Server-Sent Events สำหรับ Feed stream. |
| **Testing** | **pytest + httpx** | ใช้อยู่แล้ว. `AsyncClient` สำหรับ async routes. |
| **Docs** | **Auto-generated** | FastAPI → Swagger UI at `/docs` + ReDoc at `/redoc` |

### Why NOT Others

| Rejected | Reason |
|----------|--------|
| Node.js/Express | ต้อง HTTP bridge กลับมา Python → latency + complexity |
| Go/Gin | เร็วแต่ต้อง rewrite business logic ทั้งหมด |
| Rust/Axum | Over-engineering. ไม่ได้ต้องการ performance ระดับนั้น |
| Django REST | ใหญ่เกินไป. ORM ไม่จำเป็น (ใช้ SQLite + FalkorDB + Qdrant ตรง) |
| Flask | ไม่ async native. FastAPI ดีกว่าทุกด้าน. |
| Next.js API Routes | ไม่สามารถ import SynapseService ตรง. ต้อง HTTP hop ทุก call. |

---

## 3. Project Structure

```
synapse/
├── api/                              # ← NEW: FastAPI Gateway
│   ├── __init__.py
│   ├── main.py                       # FastAPI app + lifespan + CORS
│   ├── config.py                     # API config (port, CORS origins, API key)
│   ├── deps.py                       # Dependency injection (SynapseService, DB clients)
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                   # API key validation middleware
│   │   └── error_handler.py          # Global exception → JSON error response
│   ├── models/                       # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── memory.py                 # MemoryCreate, MemoryResponse, MemoryList
│   │   ├── graph.py                  # NodeResponse, EdgeResponse, GraphStats
│   │   ├── episode.py                # EpisodeResponse, EpisodeList
│   │   ├── procedure.py              # ProcedureCreate, ProcedureUpdate, ProcedureResponse
│   │   ├── identity.py               # IdentityContext, UserPreferences
│   │   ├── oracle.py                 # ConsultRequest, AnalyzeRequest, ReflectResponse
│   │   ├── system.py                 # StatusResponse, StatsResponse
│   │   ├── feed.py                   # FeedEvent, FeedFilter
│   │   ├── search.py                 # SearchRequest, SearchResponse
│   │   └── common.py                 # Pagination, ErrorResponse, SuccessResponse
│   ├── routes/                       # Route handlers (thin — delegate to service)
│   │   ├── __init__.py
│   │   ├── memory.py                 # /api/memory/*
│   │   ├── graph.py                  # /api/graph/*
│   │   ├── episodes.py               # /api/episodes/*
│   │   ├── procedures.py             # /api/procedures/*
│   │   ├── identity.py               # /api/identity/*
│   │   ├── oracle.py                 # /api/oracle/*
│   │   ├── system.py                 # /api/system/*
│   │   ├── feed.py                   # /api/feed/*
│   │   └── search.py                 # /api/search/*
│   ├── services/                     # Business logic layer (bridge to Synapse)
│   │   ├── __init__.py
│   │   ├── memory_service.py         # GAP: list, get-by-id, update, delete
│   │   ├── graph_service.py          # GAP: node-by-id, neighborhood, list edges
│   │   ├── episode_service.py        # GAP: list paginated, get-by-id
│   │   ├── procedure_service.py      # GAP: get-by-id, update, delete
│   │   ├── feed_service.py           # GAP: event history, SSE stream
│   │   ├── stats_service.py          # GAP: memory statistics, counts
│   │   └── maintenance_service.py    # GAP: decay maintenance, purge
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py               # Fixtures: test client, mock services
│       ├── test_memory.py
│       ├── test_graph.py
│       ├── test_episodes.py
│       ├── test_procedures.py
│       ├── test_identity.py
│       ├── test_oracle.py
│       ├── test_system.py
│       ├── test_feed.py
│       └── test_search.py
│
├── services/
│   └── synapse_service.py            # ← EXISTING: reuse directly
├── layers/
│   └── manager.py                    # ← EXISTING: reuse directly
├── graphiti/
│   └── graphiti.py                   # ← EXISTING: reuse directly
└── storage/
    └── qdrant_client.py              # ← EXISTING: reuse directly
```

---

## 4. Dependency Injection — How API Connects to Synapse

```python
# api/deps.py — ทุก route ใช้ deps นี้เพื่อเข้าถึง SynapseService

from synapse.services.synapse_service import SynapseService
from synapse.layers.manager import LayerManager

# Singleton — initialized once at startup via lifespan
_synapse_service: SynapseService | None = None

async def get_synapse_service() -> SynapseService:
    """Dependency: inject initialized SynapseService into route handlers."""
    assert _synapse_service is not None, "Service not initialized"
    return _synapse_service

# Route handlers use it like:
# async def list_memories(service: SynapseService = Depends(get_synapse_service)):
```

Key point: **ไม่ HTTP call ไป MCP Server** — import `SynapseService` ตรง
เหมือนกับที่ MCP tools ทำอยู่แล้ว แต่ expose เป็น REST endpoints

---

## 5. Complete API Specification — 39 Endpoints

### 5.1 Memory API (`/api/memory`)

```
GET    /api/memory
       Query: layer?, limit=20, offset=0, sort=created_at, order=desc
       Response: { items: Memory[], total: int, limit: int, offset: int }
       Implementation: Direct DB — query SQLite (episodic/procedural) + FalkorDB (semantic)

GET    /api/memory/:id
       Response: { memory: Memory }
       Implementation: Direct DB — lookup by UUID across all stores

POST   /api/memory
       Body: { name: str, content: str, source: str, source_description?: str, layer?: str }
       Response: { id: str, layer: str, message: str }
       Implementation: SynapseService.add_memory() ← เดิม

PUT    /api/memory/:id
       Body: { content?: str, metadata?: dict }
       Response: { memory: Memory }
       Implementation: Direct DB — update in appropriate store

DELETE /api/memory/:id
       Response: { message: str }
       Implementation: Direct DB — delete from appropriate store + vector index

POST   /api/memory/search
       Body: { query: str, layers?: str[], limit?: int }
       Response: { results: SearchResult[] }
       Implementation: SynapseService.search_memory() ← เดิม

POST   /api/memory/consolidate
       Body: { source?: str, min_access_count?: int, topics?: str[], dry_run?: bool }
       Response: { promoted: [], skipped: [], errors: [] }
       Implementation: SynapseService.consolidate() ← เดิม
```

### 5.2 Graph API (`/api/graph`)

```
GET    /api/graph/nodes
       Query: query?, type?, limit=50, offset=0
       Response: { nodes: Node[], total: int }
       Implementation:
         - ถ้ามี query → search_nodes (MCP)
         - ถ้าไม่มี → FalkorDB Cypher: MATCH (n:Entity) RETURN n SKIP $offset LIMIT $limit

GET    /api/graph/nodes/:id
       Response: { node: NodeDetail }
       Implementation: FalkorDB Cypher: MATCH (n {uuid: $id}) RETURN n

GET    /api/graph/nodes/:id/edges
       Query: direction=both, type?, limit=50
       Response: { edges: Edge[] }
       Implementation: FalkorDB Cypher: MATCH (n {uuid: $id})-[r]-(m) RETURN r, m

GET    /api/graph/edges
       Query: type?, limit=50, offset=0
       Response: { edges: Edge[], total: int }
       Implementation: FalkorDB Cypher: MATCH ()-[r:RELATES_TO]->() RETURN r

GET    /api/graph/edges/:id
       Response: { edge: EdgeDetail }
       Implementation: get_entity_edge (MCP) ← เดิม

DELETE /api/graph/nodes/:id
       Response: { message: str }
       Implementation: FalkorDB Cypher: MATCH (n {uuid: $id}) DETACH DELETE n
                       + Qdrant: delete vector by UUID

DELETE /api/graph/edges/:id
       Response: { message: str }
       Implementation: delete_entity_edge (MCP) ← เดิม
```

### 5.3 Episodes API (`/api/episodes`)

```
GET    /api/episodes
       Query: group_id?, limit=20, offset=0, sort=created_at, order=desc
       Response: { episodes: Episode[], total: int }
       Implementation:
         - Graphiti episodic: get_episodes (MCP) ← เดิม
         - Synapse episodic: SQLite direct query

GET    /api/episodes/:id
       Response: { episode: EpisodeDetail }
       Implementation:
         - Try Graphiti: EpisodicNode.get_by_uuid()
         - Fallback SQLite: SELECT * FROM episodes WHERE id = ?

DELETE /api/episodes/:id
       Response: { message: str }
       Implementation: delete_episode (MCP) ← เดิม + SQLite cleanup
```

### 5.4 Procedures API (`/api/procedures`)

```
GET    /api/procedures
       Query: trigger?, topic?, limit=20, offset=0, sort=success_count, order=desc
       Response: { procedures: Procedure[], total: int }
       Implementation:
         - ถ้ามี trigger → find_procedures (MCP)
         - ถ้าไม่มี → SQLite: SELECT * FROM procedures ORDER BY $sort LIMIT $limit OFFSET $offset

GET    /api/procedures/:id
       Response: { procedure: ProcedureDetail }
       Implementation: SQLite: SELECT * FROM procedures WHERE id = ?

POST   /api/procedures
       Body: { trigger: str, steps: str[], topics?: str[], source: str }
       Response: { id: str, message: str }
       Implementation: SynapseService.add_procedure() ← เดิม

PUT    /api/procedures/:id
       Body: { trigger?: str, steps?: str[], topics?: str[] }
       Response: { procedure: Procedure }
       Implementation: SQLite: UPDATE procedures SET ... WHERE id = ?
                       + Re-index Qdrant vector

DELETE /api/procedures/:id
       Response: { message: str }
       Implementation: SQLite: DELETE FROM procedures WHERE id = ?
                       + Qdrant: delete vector

POST   /api/procedures/:id/success
       Response: { success_count: int }
       Implementation: record_procedure_success (MCP) ← เดิม
```

### 5.5 Identity API (`/api/identity`)

```
GET    /api/identity
       Response: { user_id: str, agent_id: str|null, chat_id: str|null }
       Implementation: SynapseService.get_identity() ← เดิม

PUT    /api/identity
       Body: { user_id?: str, agent_id?: str, chat_id?: str }
       Response: { identity: Identity }
       Implementation: SynapseService.set_identity() ← เดิม

DELETE /api/identity
       Response: { previous: Identity, current: Identity }
       Implementation: SynapseService.clear_identity() ← เดิม

GET    /api/identity/preferences
       Query: user_id?
       Response: { preferences: UserPreferences }
       Implementation: SynapseService.get_user_context() ← เดิม

PUT    /api/identity/preferences
       Body: { language?, timezone?, response_style?, add_expertise?, add_topic?, add_note? }
       Response: { preferences: UserPreferences }
       Implementation: SynapseService.update_user_preferences() ← เดิม
```

### 5.6 Oracle API (`/api/oracle`)

```
POST   /api/oracle/consult
       Body: { query: str, layers?: str[], limit?: int }
       Response: { query: str, layers: dict, summary: [] }
       Implementation: SynapseService.consult() ← เดิม

POST   /api/oracle/reflect
       Body: { layer?: str }
       Response: { insights: [], source_layer: str }
       Implementation: SynapseService.reflect() ← เดิม

POST   /api/oracle/analyze
       Body: { analysis_type?: str, time_range_days?: int }
       Response: { patterns: { topics, procedures, activity, memory_distribution } }
       Implementation: SynapseService.analyze_patterns() ← เดิม
```

### 5.7 System API (`/api/system`)

```
GET    /api/system/status
       Response: { status: str, services: { falkordb: str, qdrant: str, sqlite: str } }
       Implementation: get_status (MCP) + เพิ่ม per-service health checks

GET    /api/system/stats
       Response: {
         entities: int, edges: int, episodes: int, procedures: int,
         episodic_items: int, working_keys: int,
         storage: { falkordb_mb: float, qdrant_mb: float, sqlite_mb: float }
       }
       Implementation: NEW — aggregate counts from all stores:
         - FalkorDB: MATCH (n) RETURN count(n)
         - SQLite: SELECT COUNT(*) FROM procedures / episodes
         - Qdrant: collection info API
         - Working: len(context_dict)

POST   /api/system/maintenance
       Body: { actions?: ["decay_refresh", "purge_expired", "rebuild_fts"] }
       Response: { results: { action: str, affected: int }[] }
       Implementation: NEW —
         - decay_refresh: recalculate decay scores for all items
         - purge_expired: delete episodic items past TTL
         - rebuild_fts: rebuild FTS5 indices

DELETE /api/system/graph
       Body: { confirm: true, group_ids?: str[] }
       Response: { message: str }
       Implementation: clear_graph (MCP) ← เดิม + require confirm=true
```

### 5.8 Feed API (`/api/feed`)

```
GET    /api/feed
       Query: layer?, limit=50, since?=ISO_timestamp
       Response: { events: FeedEvent[] }
       Implementation: NEW — ต้องสร้าง event log system:
         - เพิ่ม event table ใน SQLite
         - Hook into SynapseService methods เพื่อ log ทุก action
         - Query ล่าสุด N events

GET    /api/feed/stream
       Response: text/event-stream (SSE)
       Implementation: NEW — FastAPI StreamingResponse:
         - In-memory event bus (asyncio.Queue)
         - SynapseService hooks emit events
         - SSE endpoint yields events as they arrive
         - Heartbeat every 30s
```

### 5.9 Search API (`/api/search`)

```
POST   /api/search
       Body: { query: str, layers?: str[], limit?: int, date_from?: str, date_to?: str }
       Response: { results: SearchResult[] }
       Implementation: SynapseService.search_memory() ← เดิม + date filtering

POST   /api/search/graph
       Body: { query: str, entity_types?: str[], max_nodes?: int, center_node_uuid?: str }
       Response: { nodes: Node[], edges: Edge[] }
       Implementation: search_nodes + search_memory_facts (MCP) ← เดิม

POST   /api/search/vector
       Body: { query: str, collection: str, limit?: int, score_threshold?: float }
       Response: { results: VectorResult[] }
       Implementation: NEW — Qdrant direct:
         - Embed query text → vector
         - Search qdrant collection
         - Return with similarity scores
```

---

## 6. Data Models (Pydantic)

### 6.1 Common

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None

class SuccessResponse(BaseModel):
    message: str
```

### 6.2 Memory

```python
class MemoryLayer(str, Enum):
    USER = "USER_MODEL"
    PROCEDURAL = "PROCEDURAL"
    SEMANTIC = "SEMANTIC"
    EPISODIC = "EPISODIC"
    WORKING = "WORKING"

class MemoryCreate(BaseModel):
    name: str
    content: str
    source: str = "api"
    source_description: str | None = None
    layer: MemoryLayer | None = None    # auto-classify if None

class Memory(BaseModel):
    id: str
    layer: MemoryLayer
    content: str
    created_at: datetime
    decay_score: float | None = None
    access_count: int = 0
    metadata: dict = {}
```

### 6.3 Graph

```python
class EntityType(str, Enum):
    PERSON = "person"
    TECH = "tech"
    CONCEPT = "concept"
    PROJECT = "project"
    TOPIC = "topic"
    COMPANY = "company"
    PROCEDURE = "procedure"

class Node(BaseModel):
    uuid: str
    name: str
    entity_type: EntityType | None = None
    labels: list[str] = []
    created_at: datetime | None = None
    summary: str | None = None
    group_id: str | None = None
    attributes: dict = {}

class Edge(BaseModel):
    uuid: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: str | None = None
    target_node_name: str | None = None
    confidence: float = 1.0
    created_at: datetime | None = None
    is_superseded: bool = False
```

### 6.4 Feed

```python
class FeedEventType(str, Enum):
    MEMORY_ADD = "memory.add"
    MEMORY_DELETE = "memory.delete"
    MEMORY_SEARCH = "memory.search"
    MEMORY_DECAY = "memory.decay"
    PROCEDURE_ADD = "procedure.add"
    PROCEDURE_SUCCESS = "procedure.success"
    IDENTITY_CHANGE = "identity.change"
    CONSOLIDATION = "consolidation"
    MAINTENANCE = "maintenance"
    SYSTEM_ERROR = "system.error"

class FeedEvent(BaseModel):
    id: str
    type: FeedEventType
    layer: MemoryLayer | None = None
    summary: str
    detail: dict = {}
    timestamp: datetime
```

---

## 7. Event Bus — Feed System Architecture

ส่วนที่ซับซ้อนที่สุดใน GAP endpoints: **ต้องสร้าง event system ขึ้นมาใหม่**

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  SynapseService.add_memory()                                    │
│       ↓                                                         │
│  event_bus.emit(FeedEvent(type="memory.add", ...))             │
│       ↓                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ SQLite Writer │  │ SSE Broadcast│  │ In-Memory    │          │
│  │ (persist)     │  │ (stream)     │  │ Ring Buffer  │          │
│  │               │  │              │  │ (feed cache) │          │
│  │ INSERT INTO   │  │ yield event  │  │ last 500     │          │
│  │ feed_events   │  │ to all SSE   │  │ events       │          │
│  │ VALUES(...)   │  │ subscribers  │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# api/services/feed_service.py

class EventBus:
    """In-process event bus with SQLite persistence + SSE broadcast."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._ring_buffer: deque[FeedEvent] = deque(maxlen=500)
        self._db: aiosqlite.Connection | None = None

    async def emit(self, event: FeedEvent):
        """Emit event → persist + broadcast + buffer."""
        self._ring_buffer.append(event)
        await self._persist(event)
        for queue in self._subscribers:
            await queue.put(event)

    def subscribe(self) -> asyncio.Queue:
        """New SSE subscriber gets a queue."""
        queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.remove(queue)

    async def get_recent(self, limit: int = 50, layer: str = None) -> list[FeedEvent]:
        """Get recent events from ring buffer or DB."""
        ...
```

### Hook Points (เพิ่มใน SynapseService)

ไม่แก้ SynapseService โดยตรง — ใช้ decorator pattern:

```python
# api/services/event_hooks.py

def with_event_logging(event_bus: EventBus):
    """Wrap SynapseService methods to emit events."""

    original_add = service.add_memory

    async def add_memory_with_event(*args, **kwargs):
        result = await original_add(*args, **kwargs)
        await event_bus.emit(FeedEvent(
            type=FeedEventType.MEMORY_ADD,
            layer=result.get("layer"),
            summary=f"Added: {kwargs.get('name', 'unknown')}",
            detail=result,
        ))
        return result

    service.add_memory = add_memory_with_event
```

---

## 8. Authentication & Security

### API Key (ระยะแรก — single-user system)

```python
# api/middleware/auth.py

API_KEY_HEADER = "X-API-Key"

async def verify_api_key(request: Request):
    key = request.headers.get(API_KEY_HEADER)
    if not key or key != settings.api_key:
        raise HTTPException(401, "Invalid API key")
```

### Security Measures

| Measure | Implementation |
|---------|----------------|
| API Key | `X-API-Key` header required on all routes |
| CORS | Whitelist Next.js origin only (`http://localhost:3000`) |
| Rate Limiting | `slowapi` — 100 req/min per IP |
| Input Validation | Pydantic models on every request body |
| SQL Injection | Parameterized queries only (never string interpolation) |
| Destructive Ops | `DELETE /api/system/graph` requires `{ confirm: true }` in body |
| Error Sanitization | Never expose stack traces in production |

---

## 9. Docker Integration

```yaml
# docker-compose.yml — เพิ่ม API Gateway service

services:
  synapse-api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - SYNAPSE_API_KEY=${SYNAPSE_API_KEY}
      - FALKORDB_URI=redis://falkordb:6379
      - QDRANT_URL=http://qdrant:6333
      - CORS_ORIGINS=http://localhost:3000
    volumes:
      - synapse_data:/root/.synapse    # share SQLite path
    depends_on:
      synapse:
        condition: service_healthy
    networks:
      - synapse-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/system/status"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 10. Implementation Phases

### Phase 1 — Core + Pass-through (Week 1)

**เป้าหมาย:** API ที่ทำงานได้กับ 17 endpoints ที่ MCP มีอยู่แล้ว

| Task | Details |
|------|---------|
| Scaffold FastAPI project | `synapse/api/` structure ตามที่ออกแบบ |
| Pydantic models | Common, Memory, Identity, Oracle, System models |
| Dependency injection | SynapseService singleton via lifespan |
| Identity routes | GET/PUT/DELETE — pass-through to SynapseService |
| Oracle routes | consult/reflect/analyze — pass-through |
| Memory POST + search | add_memory + search_memory_layers |
| Procedures POST + find + success | pass-through |
| System status | pass-through get_status |
| Auth middleware | X-API-Key |
| CORS middleware | Allow Next.js origin |
| Docker config | Dockerfile.api + compose service |
| Tests | pytest for all pass-through routes |

**ผลลัพธ์:** 17 endpoints ใช้งานได้ — Frontend เริ่ม integrate ได้เลย

### Phase 2 — Graph + Browse (Week 2)

**เป้าหมาย:** Graph CRUD + list/browse capabilities

| Task | Details |
|------|---------|
| Graph service | FalkorDB Cypher queries สำหรับ node/edge listing |
| GET /api/graph/nodes | List + search + entity type filter |
| GET /api/graph/nodes/:id | Node detail by UUID |
| GET /api/graph/nodes/:id/edges | Neighborhood query |
| DELETE /api/graph/nodes/:id | DETACH DELETE + cleanup |
| Procedure CRUD | GET by ID, PUT update, DELETE from SQLite |
| Episode list + detail | SQLite + Graphiti combined query |
| Memory list + get-by-id | Cross-store query aggregation |
| Pagination | Generic limit/offset on all list endpoints |

**ผลลัพธ์:** Frontend Graph view + Procedures view ใช้งานได้เต็ม

### Phase 3 — Feed + Events (Week 3)

**เป้าหมาย:** Live feed system + event history

| Task | Details |
|------|---------|
| Event bus | In-memory bus + SQLite persistence |
| Service hooks | Decorator wrapping SynapseService methods |
| feed_events table | SQLite schema + queries |
| GET /api/feed | Recent events with layer filter |
| GET /api/feed/stream | SSE endpoint with heartbeat |
| System stats | Aggregate counts from all stores |
| System maintenance | Decay refresh + purge expired |
| Vector search | Direct Qdrant search endpoint |

**ผลลัพธ์:** Feed view live stream ใช้งานได้ + System dashboard เต็ม

### Phase 4 — Polish + Production (Week 4)

**เป้าหมาย:** Production readiness

| Task | Details |
|------|---------|
| Rate limiting | slowapi integration |
| Error handling | Global exception handler, error sanitization |
| Logging | Structured logging (structlog) |
| OpenAPI docs | Review + customize Swagger UI |
| Integration tests | Full e2e with running Synapse stack |
| Performance test | Load test critical endpoints |
| Docker production | Multi-stage build, health checks |
| Environment config | .env.example + documentation |

**ผลลัพธ์:** Production-ready API Gateway

---

## 11. Communication Flow — Full Stack

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌───────────┐
│          │     │              │     │              │     │           │
│  Browser │────→│  Next.js     │────→│  FastAPI     │────→│ Synapse   │
│  (React) │ JS  │  (Frontend)  │ HTTP│  (API GW)    │ Py  │ Service   │
│          │←────│              │←────│              │←────│           │
│          │     │  Port 3000   │     │  Port 8000   │     │           │
│          │     │              │     │              │     │  ┌───────┐│
│          │     │              │     │   ┌──────┐   │     │  │FalkorDB│
│          │     │              │     │   │Event │   │     │  │Qdrant ││
│          │     │              │     │   │ Bus  │   │     │  │SQLite ││
│          │     │              │     │   └──────┘   │     │  └───────┘│
└──────────┘     └──────────────┘     └──────────────┘     └───────────┘
                                                                ↑
                                      ┌──────────────┐         │
                                      │  MCP Server  │─────────┘
                                      │  Port 47780  │  (AI agents
                                      │  (JSON-RPC)  │   ใช้ทางนี้)
                                      └──────────────┘
```

### เปลี่ยนแปลงใน Frontend Plan

Frontend plan เดิมออกแบบให้ Next.js API Routes เป็น proxy → MCP Server
ตอนนี้เปลี่ยนเป็น:

```
เดิม:  Browser → Next.js API Routes → MCP Server (HTTP)
ใหม่:  Browser → Next.js (SSR/CSR) → FastAPI Gateway (HTTP :8000)
```

Next.js API routes ไม่จำเป็นแล้ว — Frontend call FastAPI ตรง via `fetch()` / TanStack Query

---

## 12. Summary

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Language:    Python 3.12+                                   │
│  Framework:   FastAPI 0.115+                                 │
│  Server:      Uvicorn (ASGI)                                 │
│  Validation:  Pydantic v2 (reuse existing models)            │
│  Auth:        X-API-Key header                               │
│  Streaming:   SSE via sse-starlette                          │
│  Testing:     pytest + httpx AsyncClient                     │
│  Docs:        Auto-generated Swagger + ReDoc                 │
│                                                              │
│  Total Endpoints:    39                                      │
│  Pass-through MCP:   17 (44%)                                │
│  Direct DB Access:   18 (46%)                                │
│  New Features:        4 (10%) — feed, stats, maintenance     │
│                                                              │
│  เหตุผลที่เลือก Python:                                      │
│  → import SynapseService ตรง ไม่ต้อง HTTP bridge             │
│  → ใช้ driver เดิม (FalkorDB, Qdrant, SQLite)               │
│  → Pydantic models reuse ได้ทั้งหมด                         │
│  → อยู่ใน container เดียวกันได้                               │
│  → ไม่ต้อง rewrite business logic แม้แต่บรรทัดเดียว          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```
