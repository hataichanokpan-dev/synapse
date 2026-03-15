# 📊 รายงานโปรเจค Synapse

> วันที่: 2026-03-15
> ผู้รายงาน: โจ 💻 และ นีโอ 🧭

---

## 1. Synapse คืออะไร?

**Synapse** = ระบบความจำสำหรับ AI (Memory Backend)

```
┌─────────────────────────────────────────────────────────────┐
│                        Cerberus                              │
│                    (AI Assistant System)                     │
│                           │                                  │
│                           ▼                                  │
│                    ┌─────────────┐                           │
│                    │   Synapse   │ ◄── คลังความจำ             │
│                    │ MCP Server  │                           │
│                    └─────────────┘                           │
│                           │                                  │
│            ┌──────────────┼──────────────┐                   │
│            ▼              ▼              ▼                   │
│     ┌──────────┐   ┌──────────┐   ┌──────────┐              │
│     │ FalkorDB │   │  Qdrant  │   │   LLM    │              │
│     │  (Graph) │   │ (Vector) │   │(Anthropic)│              │
│     └──────────┘   └──────────┘   └──────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### หน้าที่หลัก

| ฟังก์ชัน | คำอธิบาย |
|----------|----------|
| `add_memory` | บันทึกข้อมูล/ความจำใหม่ |
| `search_nodes` | ค้นหา entities (คน, สถานที่, สิ่งของ) |
| `search_memory_facts` | ค้นหาความสัมพันธ์ระหว่าง entities |
| `get_episodes` | ดึงข้อมูลที่เคยบันทึกไว้ |

---

## 2. สถานะโปรเจค

```
Phase 5: Deploy Synapse as Memory Backend for Cerberus
│
├── M1 Smoke Test ────────────────── ✅ สมบูรณ์ (2026-03-15)
│
├── M2 MCP Integration ───────────── ✅ สมบูรณ์ (2026-03-15)
│
└── M3 Production Deploy ─────────── ⏳ รอทำ
```

---

## 3. Flow การทำงานของ Synapse

### 3.1 Add Memory Flow

```
User Input: "โบ๊ทชอบเล่นเกมและทำ AI"
       │
       ▼
  ┌─────────────┐
  │ MCP Server  │  รับคำขอผ่าน HTTP/MCP protocol
  │ (port 47780)│
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │   Queue     │  ใส่คิวรอประมวลผล (ไม่บล็อกผู้ใช้)
  │   Service   │
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │    LLM      │  วิเคราะห์ข้อความ
  │ (Anthropic) │  - แยก entities (คน, สถานที่, สิ่งของ)
  │             │  - หาความสัมพันธ์ (facts)
  │             │  - สรุปข้อมูล
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │  Embedder   │  แปลงข้อความเป็น vector
  │   (Local)   │  (multilingual-e5-small, 384 dims)
  └─────┬───────┘
        │
   ┌────┴────┐
   ▼         ▼
┌─────┐  ┌───────┐
│Graph│  │Vector │  เก็บข้อมูล
│ DB  │  │ Store │  - FalkorDB: เก็บเป็นกราฟ
└─────┘  └───────┘  - Qdrant: เก็บเป็น vector
```

### 3.2 Search Flow

```
User Query: "โบ๊ทชอบทำอะไร"
       │
       ▼
  ┌─────────────┐
  │  Embedder   │  แปลงคำค้นหาเป็น vector
  │   (Local)   │
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │   Qdrant    │  ค้นหา vector ที่ใกล้เคียง (semantic search)
  │ (Vector DB) │
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │  Reranker   │  เรียงลำดับผลการค้นหาให้แม่นยำขึ้น
  │    (BGE)    │  (cross-encoder)
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │  FalkorDB   │  ดึงข้อมูลกราฟที่เกี่ยวข้อง
  │  (Graph)    │  (entities, facts, episodes)
  └─────┬───────┘
        │
        ▼
  Result: Nodes/Facts/Episodes
```

---

## 4. สิ่งที่ทำไปแล้ว

### M1: Smoke Test ✅

| ขั้นตอน | สิ่งที่ทำ | ผลลัพธ์ |
|---------|----------|---------|
| 1.1 | สร้าง Python virtual environment | ✅ .venv |
| 1.2 | สร้าง config.yaml และ .env | ✅ Ollama + Local embedder |
| 1.3 | Start Docker containers | ✅ FalkorDB + Qdrant |
| 1.4 | Start MCP server | ✅ Port 47780 |
| 1.5 | Run smoke test | ✅ 5/5 tests passed |

### M2: MCP Integration ✅

| ขั้นตอน | สิ่งที่ทำ | ปัญหาที่พบ | แก้ไข |
|---------|----------|------------|-------|
| 2.1 | Start MCP server | ✅ | - |
| 2.2 | Test connection | ✅ | - |
| 2.3 | Test add_memory | ⚠️ Episode queued แต่ไม่เก็บ | LLM model ผิด |
| 2.4 | แก้ LLM config | Z.ai model ไม่รู้จัก | เปลี่ยนเป็น Anthropic |
| 2.5 | แก้ Reranker | ต้องการ OpenAI key | ใช้ BGE (local) |
| 2.6 | ทดสอบใหม่ | ✅ | add_memory + search ทำงาน |

---

## 5. Components ที่ใช้

### 5.1 LLM (Large Language Model)

| Provider | Model | หน้าที่ |
|----------|-------|--------|
| Anthropic | GLM-5 | วิเคราะห์ข้อความ, แยก entities, สร้าง facts |

### 5.2 Embedder

| Provider | Model | Dimensions | หน้าที่ |
|----------|-------|------------|--------|
| Local | multilingual-e5-small | 384 | แปลงข้อความเป็น vector |

### 5.3 Reranker

| Provider | Model | หน้าที่ |
|----------|-------|--------|
| Local | BAAI/bge-reranker-v2-m3 | เรียงลำดับผลการค้นหา |

### 5.4 Database

| ประเภท | Product | หน้าที่ |
|--------|---------|--------|
| Graph Database | FalkorDB | เก็บ entities, facts, episodes |
| Vector Store | Qdrant | เก็บ embeddings สำหรับ search |

---

## 6. ไฟล์สำคัญ

```
C:/Programing/PersonalAI/synapse/
│
├── synapse/mcp_server/
│   ├── config/
│   │   └── config.yaml      ← LLM, Embedder, Database config
│   ├── .env                 ← API keys
│   ├── main.py              ← Entry point
│   └── src/
│       ├── graphiti_mcp_server.py  ← MCP server logic
│       └── services/
│           └── factories.py        ← Create LLM/Embedder clients
│
├── synapse/graphiti/
│   ├── embedder/
│   │   └── local.py         ← LocalEmbedder class
│   └── cross_encoder/
│       └── bge_reranker_client.py  ← BGE Reranker
│
└── docker-compose.yml       ← FalkorDB + Qdrant
```

---

## 7. ปัญหาที่แก้ไขแล้ว

| # | ปัญหา | สาเหตุ | แก้ไข |
|---|-------|--------|------|
| 1 | Z.ai API ไม่รองรับ Responses API | OpenAIClient ใช้ responses.parse | ใช้ OpenAIGenericClient |
| 2 | Z.ai ไม่รู้จัก model llama3.2 | model name ผิด | เปลี่ยนเป็น Anthropic |
| 3 | Reranker ต้องการ OpenAI key | cross_encoder default ใช้ OpenAI | ใช้ BGE Reranker (local) |
| 4 | Episode ไม่เข้า database | LLM error ทำให้ processing fail | แก้ LLM config |
| 5 | group_id มี hyphen | RediSearch ไม่รองรับ | ใช้ group_id ไม่มี hyphen |

---

## 8. ขั้นต่อไป (M3: Production Deploy)

| # | Task | รายละเอียด |
|---|------|-----------|
| 3.1 | Docker Compose | สร้าง production-ready compose |
| 3.2 | Environment | Config สำหรับ production |
| 3.3 | Deploy | Deploy full stack |
| 3.4 | Benchmark | ทดสอบ performance |
| 3.5 | Cerberus Integration | เชื่อมกับ Cerberus จริง |

---

## 9. Quick Commands

```bash
# Start Docker containers
cd C:/Programing/PersonalAI/synapse
docker compose up -d falkordb qdrant

# Start MCP server
.venv/Scripts/synapse-mcp --config synapse/mcp_server/config/config.yaml --transport http --port 47780

# Test health
curl http://localhost:47780/health
```

---

## 10. สรุป

| หัวข้อ | สถานะ |
|--------|-------|
| **โปรเจค** | Synapse = Memory Backend สำหรับ AI |
| **ความคืบหน้า** | M1 ✅, M2 ✅, M3 ⏳ |
| **ทำงานได้ไหม** | ✅ ได้ (add_memory, search_nodes, get_episodes) |
| **ปัญหาคงเหลือ** | ไม่มี (แก้หมดแล้ว) |
| **พร้อม production** | ยังไม่พร้อม (ต้องทำ M3) |
