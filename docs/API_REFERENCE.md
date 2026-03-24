# Synapse API Reference

> คู่มือการใช้งาน API สำหรับ Frontend Developer  
> Base URL: `http://localhost:8000`  
> Interactive Docs: `http://localhost:8000/docs` (Swagger UI)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System](#1-system)
3. [Identity](#2-identity)
4. [Memory](#3-memory)
5. [Procedures](#4-procedures)
6. [Graph](#5-graph)
7. [Episodes](#6-episodes)
8. [Feed](#7-feed)
9. [Oracle](#8-oracle)
10. [Error Handling](#error-handling)
11. [TypeScript Types](#typescript-types)

---

## Architecture Overview

```
Browser (Next.js) → FastAPI (:8000) → SynapseService → FalkorDB / Qdrant / SQLite
```

**CORS**: All origins allowed in dev mode.  
**Auth**: Optional API key via `X-API-Key` header.
**Runtime storage note**: local defaults use `~/.synapse`, but Docker deployments use `/app/.synapse` as the canonical SQLite runtime store. Host-side `~/.synapse` is not the source of truth unless it is mounted to that path inside the container.

---

## 1. System

### GET /api/system/status
ตรวจสอบสถานะของระบบทั้งหมด

**Response:**
```json
{
  "status": "degraded",
  "message": "Some components degraded",
  "components": [
    {
      "name": "falkordb",
      "status": "degraded",
      "latency_ms": null,
      "message": "not initialized",
      "details": {}
    },
    {
      "name": "layer_manager",
      "status": "healthy",
      "latency_ms": null,
      "message": "ok",
      "details": {}
    },
    {
      "name": "episodic_db",
      "status": "healthy",
      "latency_ms": null,
      "message": "ok",
      "details": {}
    },
    {
      "name": "procedural_db",
      "status": "healthy",
      "latency_ms": null,
      "message": "ok",
      "details": {}
    },
    {
      "name": "semantic_outbox_graph",
      "status": "degraded",
      "latency_ms": null,
      "message": "degraded: pending=3, failed=3, dead_letter=0, circuit=paused_by_rate_limit",
      "details": {
        "pending_count": 3,
        "failed_count": 3,
        "due_count": 1,
        "dead_letter_count": 0,
        "leased_count": 0,
        "circuit_state": "paused_by_rate_limit",
        "cooldown_until": "2026-03-24T01:25:00Z",
        "last_error_code": "RATE_LIMIT",
        "provider_last_429_at": "2026-03-24T01:20:00Z",
        "last_projected_at": "2026-03-24T01:10:00Z",
        "next_attempt_at": "2026-03-24T01:20:00Z"
      }
    },
    {
      "name": "semantic_outbox_vector",
      "status": "healthy",
      "latency_ms": null,
      "message": "ok",
      "details": {}
    },
    {
      "name": "hybrid_search",
      "status": "degraded",
      "latency_ms": null,
      "message": "degraded: graph",
      "details": {}
    }
  ]
}
```

`semantic_outbox_graph` และ `semantic_outbox_vector` ใช้บอกสถานะ background projection แยกตาม backend โดยตรง ไม่ต้องเดาจาก status รวมของ `hybrid_search`

**Frontend Usage:**
```typescript
const res = await fetch("/api/system/status");
const data: StatusResponse = await res.json();
const isHealthy = data.status === "healthy";
```

---

### GET /api/system/stats
สถิติการใช้งานหน่วยความจำทั้งหมด

**Response:**
```json
{
  "memory": {
    "entities": 0,
    "edges": 0,
    "episodes": 0,
    "procedures": 327,
    "episodic_items": 0,
    "working_keys": 0,
    "user_models": 0
  },
  "storage": {
    "falkordb_mb": 0.0,
    "qdrant_mb": 0.0,
    "sqlite_mb": 0.18
  },
  "search": {
    "counts": {},
    "latency_ms": {},
    "semantic_projection": {
      "nodes": 12,
      "edges": 8,
      "outbox": {
        "graph": {
          "pending_count": 3,
          "failed_count": 3,
          "due_count": 1,
          "dead_letter_count": 0,
          "leased_count": 0,
          "lag_seconds": 742.6,
          "unhealthy": true,
          "oldest_active_at": "2026-03-24T01:15:00Z",
          "oldest_due_at": "2026-03-24T01:15:00Z",
          "next_attempt_at": "2026-03-24T01:20:00Z",
          "last_error_excerpt": "429 rate limit exceeded",
          "circuit_state": "paused_by_rate_limit",
          "cooldown_until": "2026-03-24T01:25:00Z",
          "last_error_code": "RATE_LIMIT",
          "provider_last_429_at": "2026-03-24T01:20:00Z",
          "last_projected_at": "2026-03-24T01:10:00Z"
        },
        "vector": {
          "pending_count": 0,
          "failed_count": 0,
          "lag_seconds": 0.0,
          "unhealthy": false,
          "oldest_active_at": null,
          "next_attempt_at": null,
          "last_error_excerpt": null
        }
      }
    }
  },
  "last_updated": "2026-03-18T15:05:54.305168"
}
```

---

### POST /api/system/maintenance
เรียกใช้งาน maintenance tasks

**Request:**
```json
{
  "actions": ["replay_semantic_outbox", "rebuild_semantic_graph"],
  "dry_run": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `actions` | array[string] | Yes | รายการ action ที่ต้องการรัน: `decay_refresh`, `purge_expired`, `rebuild_fts`, `vacuum_sqlite`, `replay_semantic_outbox`, `rebuild_semantic_graph`, `pause_graph_projection`, `resume_graph_projection`, `replay_dead_letter_graph` |
| `dry_run` | boolean | No | `true` = preview only (default: `false`) |

**Response:**
```json
{
  "results": [
    {
      "action": "replay_semantic_outbox",
      "affected": 3,
      "duration_ms": 0.0,
      "success": true,
      "message": "Would replay 3 due semantic outbox tasks (graph=3)"
    },
    {
      "action": "rebuild_semantic_graph",
      "affected": 12,
      "duration_ms": 0.0,
      "success": true,
      "message": "Would rebuild 12 semantic graph projection records (nodes=9, edges=3)"
    }
  ],
  "total_duration_ms": 0.0,
  "dry_run": true,
  "completed_at": "2026-03-18T15:05:56.335123"
}
```

`replay_semantic_outbox` ใช้ trigger งานที่ถึงเวลาใน `semantic_outbox` ให้ลองใหม่ทันที ส่วน `rebuild_semantic_graph` ใช้สร้างงาน graph projection ใหม่จาก SQLite truth store แบบ idempotent

`pause_graph_projection` และ `resume_graph_projection` ใช้ควบคุม graph projector ตอน incident/recovery ส่วน `replay_dead_letter_graph` ใช้ requeue งาน graph ที่ถูกย้ายไป `dead_letter`

---

### DELETE /api/system/graph
ลบข้อมูล Graph ทั้งหมด (ใช้ด้วยความระวัง!)

**Request:**
```json
{
  "confirm": true
}
```

---

## 2. Identity

### GET /api/identity/
ดึงข้อมูลตัวตนของผู้ใช้งานปัจจุบัน

**Response:**
```json
{
  "user_id": "cerberus",
  "agent_id": null,
  "chat_id": null,
  "set_at": null
}
```

---

### PUT /api/identity/
ตั้งค่าตัวตนผู้ใช้

**Request:**
```json
{
  "user_id": "cerberus",
  "agent_id": "my-agent",
  "chat_id": "chat-001"
}
```

---

### DELETE /api/identity/
ลบข้อมูลตัวตน

---

### GET /api/identity/preferences
ดึงค่าความชอบของผู้ใช้

**Response:**
```json
{
  "user_id": "cerberus",
  "preferences": {
    "language": "th",
    "timezone": "Asia/Bangkok",
    "response_style": "concise",
    "expertise": [],
    "topics": [],
    "notes": "",
    "custom": {}
  },
  "updated_at": "2026-03-18T15:03:17.075813Z"
}
```

| Field | Type | Values |
|-------|------|--------|
| `response_style` | string | `concise`, `detailed`, `balanced` |
| `language` | string | ISO language code (e.g. `th`, `en`) |
| `timezone` | string | IANA timezone (e.g. `Asia/Bangkok`) |
| `expertise` | string[] | List of expertise areas |
| `topics` | string[] | List of topics of interest |
| `notes` | string | Free-form notes |

---

### PUT /api/identity/preferences
อัปเดตค่าความชอบ

**Request:**
```json
{
  "response_style": "concise",
  "language": "th",
  "timezone": "Asia/Bangkok"
}
```

**Response:**
```json
{
  "user_id": "cerberus",
  "preferences": {
    "language": "th",
    "timezone": "Asia/Bangkok",
    "response_style": "concise",
    "expertise": [],
    "topics": [],
    "notes": "",
    "custom": {}
  },
  "updated_at": "2026-03-18T15:03:17.075813Z"
}
```

---

## 3. Memory

### GET /api/memory/
แสดงรายการ Memory ทั้งหมด (pagination)

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `layer` | string | None | Filter by layer: `EPISODIC`, `PROCEDURAL`, `SEMANTIC`, `WORKING`, `USER_MODEL` |
| `limit` | int | 20 | Max items (1-100) |
| `offset` | int | 0 | Skip items |
| `sort` | string | `created_at` | Sort field: `created_at`, `name`, `access_count` |
| `order` | string | `desc` | `asc` or `desc` |

**Response:**
```json
{
  "items": [
    {
      "uuid": "8126966d-df24-4cc3-89ff-c06587854f91",
      "layer": "PROCEDURAL",
      "name": "how to test api",
      "content": "step 1\nstep 2",
      "source": "api",
      "source_description": "Procedure: how to test api",
      "group_id": null,
      "agent_id": null,
      "access_count": 0,
      "decay_score": null,
      "metadata": {
        "trigger": "how to test api",
        "steps": ["step 1", "step 2"],
        "topics": []
      },
      "tags": [],
      "created_at": null,
      "updated_at": null,
      "last_accessed": null
    }
  ],
  "total": 327,
  "limit": 20,
  "offset": 0
}
```

**Frontend Usage:**
```typescript
const res = await fetch("/api/memory/?limit=20&offset=0&layer=PROCEDURAL");
const data: MemoryListResponse = await res.json();
```

---

### GET /api/memory/{memory_id}
ดึง Memory ตาม ID

**Response:** เหมือน item ใน list ข้างบน

---

### POST /api/memory/
เพิ่ม Memory ใหม่

**Request:**
```json
{
  "name": "Meeting Notes",
  "content": "Discussed project timeline and deliverables",
  "layer": "EPISODIC",
  "source": "api",
  "source_description": "From daily standup",
  "metadata": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | ชื่อ Memory (1-200 chars) |
| `content` | string | **Yes** | เนื้อหา |
| `layer` | string | No | Target layer (auto-detect if null) |
| `source` | string | No | Source identifier (default: `api`) |
| `source_description` | string | No | Human-readable source |
| `group_id` | string | No | Group identifier |
| `agent_id` | string | No | Agent identifier |
| `metadata` | object | No | Additional metadata |

**Response:**
```json
{
  "uuid": "abc-123",
  "layer": "EPISODIC",
  "name": "Meeting Notes",
  "content": "Discussed project timeline and deliverables",
  "source": "api",
  "source_description": "From daily standup",
  "group_id": null,
  "agent_id": null,
  "access_count": 0,
  "decay_score": null,
  "metadata": {},
  "tags": [],
  "created_at": null,
  "updated_at": null,
  "last_accessed": null
}
```

---

### PUT /api/memory/{memory_id}
อัปเดต Memory

**Request:**
```json
{
  "content": "Updated content",
  "metadata": { "priority": "high" }
}
```

---

### DELETE /api/memory/{memory_id}
ลบ Memory

**Response:**
```json
{
  "status": "ok",
  "message": "Memory deleted"
}
```

---

### POST /api/memory/search
ค้นหา Memory ข้ามทุก Layer

**Request:**
```json
{
  "query": "Python programming",
  "layers": ["PROCEDURAL", "EPISODIC"],
  "limit": 10
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | **Yes** | Search query (1-500 chars) |
| `layers` | string[] | No | Filter layers (null = all) |
| `limit` | int | No | Max results (1-50, default: 10) |

**Response:**
```json
{
  "results": [
    {
      "uuid": "58734e1a-d0d1-48f6-ba25-d418c6eb62b6",
      "layer": "PROCEDURAL",
      "name": "test",
      "content": "step instructions...",
      "score": 1.0,
      "highlight": null,
      "metadata": {}
    }
  ],
  "total": 5,
  "query": "Python programming",
  "layers_searched": ["PROCEDURAL", "EPISODIC"]
}
```

---

### POST /api/memory/consolidate
รวม Memory (promote episodic → semantic)

**Request:**
```json
{
  "source": "episodic",
  "min_access_count": 2,
  "topics": ["python"],
  "dry_run": true
}
```

**Response:**
```json
{
  "promoted": [],
  "skipped": [],
  "errors": [],
  "dry_run": true
}
```

---

## 4. Procedures

### GET /api/procedures/
แสดงรายการ Procedure ทั้งหมด

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `trigger` | string | None | Filter by trigger pattern |
| `topic` | string | None | Filter by topic |
| `limit` | int | 20 | Max items (1-100) |
| `offset` | int | 0 | Skip items |

**Response:**
```json
{
  "items": [
    {
      "uuid": "8126966d-df24-4cc3-89ff-c06587854f91",
      "trigger": "how to deploy",
      "steps": ["build", "test", "deploy"],
      "topics": [],
      "source": "api",
      "source_description": "Procedure: how to deploy",
      "success_count": 0,
      "failure_count": 0,
      "decay_score": null,
      "metadata": {},
      "created_at": null,
      "updated_at": null,
      "last_used": null
    }
  ],
  "total": 327,
  "limit": 20,
  "offset": 0
}
```

---

### POST /api/procedures/
เพิ่ม Procedure ใหม่

**Request:**
```json
{
  "trigger": "how to deploy to production",
  "steps": ["build the project", "run tests", "deploy to server"],
  "topics": ["deployment", "CI/CD"],
  "source": "api"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trigger` | string | **Yes** | เงื่อนไขที่จะ trigger procedure |
| `steps` | string[] | **Yes** | ขั้นตอนการทำงาน |
| `topics` | string[] | No | หัวข้อที่เกี่ยวข้อง |
| `source` | string | No | `explicit`, `correction`, `repeated_pattern` |

**Response:**
```json
{
  "uuid": "new-id",
  "trigger": "how to deploy to production",
  "steps": ["build the project", "run tests", "deploy to server"],
  "topics": ["deployment", "CI/CD"],
  "source": "api",
  "source_description": null,
  "success_count": 0,
  "failure_count": 0,
  "decay_score": null,
  "metadata": {},
  "created_at": null,
  "updated_at": null,
  "last_used": null
}
```

---

### GET /api/procedures/{procedure_id}
ดึง Procedure ตาม ID

---

### PUT /api/procedures/{procedure_id}
อัปเดต Procedure

**Request:**
```json
{
  "steps": ["updated step 1", "updated step 2"],
  "topics": ["new-topic"]
}
```

---

### DELETE /api/procedures/{procedure_id}
ลบ Procedure

---

### POST /api/procedures/{trigger}/success
บันทึกว่า Procedure ถูกใช้งานสำเร็จ

**Example:** `POST /api/procedures/how%20to%20deploy/success`

**Response:**
```json
{
  "uuid": "proc-id",
  "trigger": "how to deploy",
  "success_count": 5
}
```

---

## 5. Graph

### GET /api/graph/nodes
ดึง Node ทั้งหมดจาก Knowledge Graph

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max nodes (1-200) |
| `offset` | int | 0 | Skip nodes |

**Response:**
```json
{
  "nodes": [
    {
      "uuid": "node-1",
      "name": "Python",
      "labels": ["Entity"],
      "properties": {},
      "created_at": "2026-03-18T12:00:00"
    }
  ],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

---

### GET /api/graph/nodes/{node_id}
ดึง Node ตาม ID

---

### GET /api/graph/nodes/{node_id}/edges
ดึง Edge ทั้งหมดที่เชื่อมกับ Node นี้

---

### GET /api/graph/edges
ดึง Edge ทั้งหมด

**Response:**
```json
{
  "edges": [
    {
      "uuid": "edge-1",
      "source_node_uuid": "node-1",
      "target_node_uuid": "node-2",
      "name": "KNOWS",
      "fact": "Python is used for data science",
      "properties": {},
      "created_at": "2026-03-18T12:00:00"
    }
  ],
  "total": 0,
  "limit": 50,
  "offset": 0
}
```

---

### GET /api/graph/edges/{edge_id}
ดึง Edge ตาม ID

---

### DELETE /api/graph/nodes/{node_id}
ลบ Node

---

### DELETE /api/graph/edges/{edge_id}
ลบ Edge

---

## 6. Episodes

### GET /api/episodes/
แสดงรายการ Episode ทั้งหมด

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 20 | Max episodes |
| `offset` | int | 0 | Skip episodes |

**Response:**
```json
{
  "episodes": [
    {
      "uuid": "ep-1",
      "name": "Daily standup discussion",
      "content": "Discussed project timeline...",
      "source": "api",
      "created_at": "2026-03-18T12:00:00"
    }
  ],
  "total": 0,
  "limit": 20,
  "offset": 0
}
```

---

### GET /api/episodes/{episode_id}
ดึง Episode ตาม ID

---

### DELETE /api/episodes/{episode_id}
ลบ Episode

---

## 7. Feed

### GET /api/feed/
ดึง Feed events (ประวัติกิจกรรม)

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `layer` | string | None | Filter by layer |
| `limit` | int | 20 | Max events (1-100) |
| `since` | string | None | ISO datetime filter (events after this time) |

**Response:**
```json
{
  "events": [
    {
      "id": "evt-2",
      "type": "procedure.add",
      "layer": "PROCEDURAL",
      "action": "ADD",
      "summary": "Added procedure: how to deploy",
      "title": null,
      "source": null,
      "detail": {
        "uuid": null,
        "trigger": "how to deploy",
        "steps": ["build", "test", "deploy"]
      },
      "metadata": {
        "uuid": null,
        "trigger": "how to deploy",
        "steps": ["build", "test", "deploy"]
      },
      "timestamp": "2026-03-18T15:06:40.123456"
    }
  ],
  "total": 2,
  "has_more": false
}
```

**Frontend Usage:**
```typescript
// ดึง feed ล่าสุด
const res = await fetch("/api/feed/?limit=50");
const data: FeedResponse = await res.json();

// Filter by layer
const res2 = await fetch("/api/feed/?layer=PROCEDURAL&limit=20");

// ดึงเฉพาะ events ใหม่หลังจาก timestamp
const res3 = await fetch("/api/feed/?since=2026-03-18T12:00:00");
```

---

### GET /api/feed/stream
SSE (Server-Sent Events) stream สำหรับ real-time updates

**Frontend Usage:**
```typescript
const eventSource = new EventSource("/api/feed/stream?api_key=YOUR_API_KEY");

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("New event:", data);
};

eventSource.onerror = () => {
  eventSource.close();
};
```

Graph projector จะ emit event types ต่อไปนี้ใน stream นี้:
- `graph.projection.queued`
- `graph.projection.completed`
- `graph.projection.failed`
- `graph.circuit.open`
- `graph.circuit.closed`

---

## 8. Oracle

### POST /api/oracle/consult
ปรึกษาระบบ Memory เพื่อหาคำตอบ

**Request:**
```json
{
  "query": "what do I know about Python?",
  "layers": ["PROCEDURAL", "EPISODIC"],
  "limit": 5
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | **Yes** | คำถามหรือหัวข้อ (1-1000 chars) |
| `layers` | string[] | No | Layer ที่จะค้นหา (null = all) |
| `limit` | int | No | Max results per layer (1-50, default: 10) |

**Response:**
```json
{
  "query": "what do I know about Python?",
  "layers": {
    "procedural": {
      "layer": "PROCEDURAL",
      "count": 5,
      "top_results": [
        {
          "preview": "trigger='python deployment' steps=['install deps', 'run tests']",
          "type": "ProceduralMemory"
        }
      ],
      "relevance_score": null
    },
    "user_model": {
      "layer": "USER_MODEL",
      "count": 0,
      "top_results": [],
      "relevance_score": null
    }
  },
  "summary": ["procedural: 5 results", "user_model: 0 results"],
  "suggestions": [],
  "consulted_at": "2026-03-18T15:06:50.123456"
}
```

---

### POST /api/oracle/reflect
สะท้อนความคิดแบบสุ่มจาก Memory

**Request:**
```json
{
  "layer": "PROCEDURAL",
  "count": 3
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `layer` | string | No | Layer เฉพาะ (null = all) |
| `count` | int | No | จำนวน insights (1-10, default: 3) |

**Response:**
```json
{
  "insights": [
    {
      "content": "Procedure: deploy → ['build', 'test', 'deploy']",
      "layer": "PROCEDURAL",
      "source": "procedure",
      "relevance": 1.0,
      "created_at": null
    }
  ],
  "source_layer": "all",
  "reflected_at": "2026-03-18T15:06:55.123456"
}
```

---

### POST /api/oracle/analyze
วิเคราะห์ Pattern จาก Memory

**Request:**
```json
{
  "analysis_type": "all",
  "time_range_days": 30
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `analysis_type` | string | **Yes** | `topics`, `procedures`, `activity`, `memory_distribution`, `all` |
| `time_range_days` | int | No | ช่วงเวลาย้อนหลัง (default: 30) |

**Response:**
```json
{
  "time_range_days": 30,
  "patterns": {
    "topics": {},
    "procedures": {
      "total": 327,
      "by_source": { "explicit": 327 },
      "most_used": [],
      "never_used": 327
    },
    "activity": {},
    "memory_distribution": {
      "episodic": 0,
      "procedural": 327,
      "semantic": 0,
      "working": 0,
      "user_model": 0
    }
  }
}
```

---

## Error Handling

ทุก Error จะมีรูปแบบเดียวกัน:

```json
{
  "error": "Internal server error",
  "detail": "An internal error occurred",
  "code": "INTERNAL_ERROR",
  "stack": null
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `404` | Resource not found |
| `422` | Validation error (missing/invalid fields) |
| `500` | Internal server error |

### 422 Validation Error Example:
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "name"],
      "msg": "Field required",
      "input": { "content": "test" }
    }
  ]
}
```

---

## TypeScript Types

สำหรับใช้ใน Frontend (ดูเพิ่มใน `synapse-ui/lib/api-client.ts`):

```typescript
// === Memory Layer Enum ===
type MemoryLayer = "EPISODIC" | "PROCEDURAL" | "SEMANTIC" | "WORKING" | "USER_MODEL";

// === System ===
interface StatusResponse {
  status: "healthy" | "degraded" | "unhealthy";
  message: string;
  components: Array<{
    name: string;
    status: "healthy" | "unhealthy";
    latency_ms: number | null;
    message: string;
    details: Record<string, unknown>;
  }>;
}

interface StatsResponse {
  memory: {
    entities: number;
    edges: number;
    episodes: number;
    procedures: number;
    episodic_items: number;
    working_keys: number;
    user_models: number;
  };
  storage: {
    falkordb_mb: number;
    qdrant_mb: number;
    sqlite_mb: number;
  };
  last_updated: string;
}

// === Identity ===
interface IdentityResponse {
  user_id: string;
  agent_id: string | null;
  chat_id: string | null;
  set_at: string | null;
}

interface UserPreferences {
  language: string;
  timezone: string;
  response_style: "concise" | "detailed" | "balanced";
  expertise: string[];
  topics: string[];
  notes: string;
  custom: Record<string, unknown>;
}

interface PreferencesResponse {
  user_id: string;
  preferences: UserPreferences;
  updated_at: string;
}

// === Memory ===
interface MemoryEntry {
  uuid: string;
  layer: MemoryLayer;
  name: string;
  content: string;
  source: string;
  source_description: string | null;
  group_id: string | null;
  agent_id: string | null;
  access_count: number;
  decay_score: number | null;
  metadata: Record<string, unknown>;
  tags: string[];
  created_at: string | null;
  updated_at: string | null;
  last_accessed: string | null;
}

interface MemoryListResponse {
  items: MemoryEntry[];
  total: number;
  limit: number;
  offset: number;
}

interface MemorySearchResult {
  uuid: string;
  layer: MemoryLayer;
  name: string;
  content: string;
  score: number;
  highlight: string | null;
  metadata: Record<string, unknown>;
}

interface MemorySearchResponse {
  results: MemorySearchResult[];
  total: number;
  query: string;
  layers_searched: string[];
}

// === Procedures ===
interface ProcedureEntry {
  uuid: string;
  trigger: string;
  steps: string[];
  topics: string[];
  source: string;
  source_description: string | null;
  success_count: number;
  failure_count: number;
  decay_score: number | null;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  last_used: string | null;
}

interface ProcedureListResponse {
  items: ProcedureEntry[];
  total: number;
  limit: number;
  offset: number;
}

// === Graph ===
interface GraphNode {
  uuid: string;
  name: string;
  labels: string[];
  properties: Record<string, unknown>;
  created_at: string;
}

interface GraphEdge {
  uuid: string;
  source_node_uuid: string;
  target_node_uuid: string;
  name: string;
  fact: string;
  properties: Record<string, unknown>;
  created_at: string;
}

// === Feed ===
interface FeedEvent {
  id: string;
  type: string;
  layer: MemoryLayer;
  action: "ADD" | "UPDATE" | "DELETE" | "SEARCH" | "CONSOLIDATE" | "MAINTENANCE" | "OTHER";
  summary: string;
  title: string | null;
  source: string | null;
  detail: Record<string, unknown>;
  metadata: Record<string, unknown>;
  timestamp: string;
}

interface FeedResponse {
  events: FeedEvent[];
  total: number;
  has_more: boolean;
}

// === Oracle ===
interface LayerSummary {
  layer: MemoryLayer;
  count: number;
  top_results: Array<Record<string, unknown>>;
  relevance_score: number | null;
}

interface ConsultResponse {
  query: string;
  layers: Record<string, LayerSummary>;
  summary: string[];
  suggestions: string[];
  consulted_at: string;
}

interface Insight {
  content: string;
  layer: MemoryLayer;
  source: string;
  relevance: number;
  created_at: string | null;
}

interface ReflectResponse {
  insights: Insight[];
  source_layer: string;
  reflected_at: string;
}

interface AnalyzeResponse {
  time_range_days: number;
  patterns: Record<string, unknown>;
}

// === Consolidate ===
interface ConsolidateRequest {
  source?: string;
  min_access_count?: number;
  topics?: string[];
  dry_run?: boolean;
}

interface ConsolidateResponse {
  promoted: unknown[];
  skipped: unknown[];
  errors: unknown[];
  dry_run: boolean;
}
```

---

## Quick Reference: All Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/system/status` | Health check |
| GET | `/api/system/stats` | Memory statistics |
| POST | `/api/system/maintenance` | Run maintenance |
| DELETE | `/api/system/graph` | Clear graph data |
| GET | `/api/identity/` | Get identity |
| PUT | `/api/identity/` | Set identity |
| DELETE | `/api/identity/` | Clear identity |
| GET | `/api/identity/preferences` | Get preferences |
| PUT | `/api/identity/preferences` | Update preferences |
| GET | `/api/memory/` | List memories |
| GET | `/api/memory/{id}` | Get memory by ID |
| POST | `/api/memory/` | Add memory |
| PUT | `/api/memory/{id}` | Update memory |
| DELETE | `/api/memory/{id}` | Delete memory |
| POST | `/api/memory/search` | Search memories |
| POST | `/api/memory/consolidate` | Consolidate memories |
| GET | `/api/procedures/` | List procedures |
| POST | `/api/procedures/` | Add procedure |
| GET | `/api/procedures/{id}` | Get procedure by ID |
| PUT | `/api/procedures/{id}` | Update procedure |
| DELETE | `/api/procedures/{id}` | Delete procedure |
| POST | `/api/procedures/{trigger}/success` | Record success |
| GET | `/api/graph/nodes` | List nodes |
| GET | `/api/graph/nodes/{id}` | Get node |
| GET | `/api/graph/nodes/{id}/edges` | Get node edges |
| GET | `/api/graph/edges` | List edges |
| GET | `/api/graph/edges/{id}` | Get edge |
| DELETE | `/api/graph/nodes/{id}` | Delete node |
| DELETE | `/api/graph/edges/{id}` | Delete edge |
| GET | `/api/episodes/` | List episodes |
| GET | `/api/episodes/{id}` | Get episode |
| DELETE | `/api/episodes/{id}` | Delete episode |
| GET | `/api/feed/` | Get feed events |
| GET | `/api/feed/stream` | SSE real-time stream |
| POST | `/api/oracle/consult` | Consult memory |
| POST | `/api/oracle/reflect` | Random reflection |
| POST | `/api/oracle/analyze` | Analyze patterns |
