# Synapse Capabilities, System Flow, and Differentiators

ชื่อเอกสาร: Synapse Capabilities, System Flow, and Differentiators  
วันที่: 2026-03-21  
ภาษา: ไทย + English  
ขอบเขต: อธิบายว่า Synapse ทำอะไรได้บ้าง, flow ปัจจุบันเป็นอย่างไร, และดีกว่าแนวทาง memory/RAG แบบอื่นอย่างไร โดยอิงจากระบบที่มีอยู่จริงใน repository นี้

---

## 1. Executive Summary / สรุปสำหรับผู้บริหาร

### TH

`Synapse` คือระบบ memory และ context runtime สำหรับ Personal AI ที่พยายามทำมากกว่า "vector search + chat history".

ในเชิงโครงสร้าง Synapse มี memory หลายชนิด, มี API สำหรับ CRUD/search/maintenance, รองรับ `SQLite` เป็น baseline truth store, และสามารถต่อกับ `Qdrant` และ `Graphiti/FalkorDB` เพื่อเพิ่มความสามารถด้าน semantic retrieval และ graph reasoning ได้

จุดเด่นของ Synapse ไม่ได้อยู่ที่มี vector search อย่างเดียว แต่อยู่ที่:

- แยก memory เป็นหลาย layer ตามหน้าที่
- เก็บข้อมูลระยะสั้นและระยะยาวต่างกัน
- รองรับทั้ง CRUD, search, feed, maintenance, identity, episodes, procedures
- ใช้งานได้แม้ backend ขั้นสูงจะปิดอยู่
- เริ่มมีแนวทางไปสู่ `Personal Brain Runtime` มากกว่าระบบ RAG ทั่วไป

อย่างไรก็ตาม ณ ตอนนี้ Synapse ยังไม่ควรถูกอธิบายว่าเป็น "สมองสมบูรณ์แบบ" หรือ "true hybrid ranking engine" เพราะ:

- การ search ยังเป็น `multi-backend retrieval + fallback` มากกว่า full score fusion
- ยังไม่มี query-time context compiler ที่สมบูรณ์
- goals, projects, trust controls, reflective consolidation ระดับลึก ยังอยู่ใน roadmap

### EN

`Synapse` is a memory and context runtime for Personal AI that aims to go beyond "vector search + chat history".

Architecturally, Synapse has multiple memory types, API support for CRUD/search/maintenance, `SQLite` as a baseline durable truth store, and optional integrations with `Qdrant` and `Graphiti/FalkorDB` for semantic retrieval and graph-backed reasoning.

Its strength is not merely that it has vector search. Its strength is that it:

- separates memory into functional layers
- distinguishes short-term and long-term memory roles
- exposes CRUD, search, feed, maintenance, identity, episode, and procedure flows
- remains usable even when advanced backends are disabled
- already points toward a `Personal Brain Runtime`, not just a generic RAG service

That said, Synapse should not yet be described as a complete "personal brain" or a "true hybrid ranking engine" because:

- search is currently closer to `multi-backend retrieval + fallback` than full score fusion
- there is no fully implemented query-time context compiler yet
- goals, projects, trust controls, and deep reflective consolidation are still roadmap items

---

## 2. What Synapse Can Do Today / Synapse ทำอะไรได้บ้างตอนนี้

### TH

จากระบบ API และ layer manager ปัจจุบัน Synapse สามารถทำสิ่งสำคัญได้ดังนี้

#### 2.1 Memory CRUD

- เพิ่ม memory ผ่าน `POST /api/memory`
- ดึงรายการ memory ผ่าน `GET /api/memory`
- ดู memory รายตัวผ่าน `GET /api/memory/{id}`
- ค้นหา memory ผ่าน `POST /api/memory/search`
- แก้ไข memory ผ่าน `PUT /api/memory/{id}`
- ลบ memory ผ่าน `DELETE /api/memory/{id}`
- consolidate memory ผ่าน `POST /api/memory/consolidate`

สิ่งที่ใช้งานได้จริงตอนนี้:

- `request.layer` สามารถ override classifier ได้
- create/update response คืน persisted state ที่น่าเชื่อถือขึ้น
- procedural และ episodic CRUD ใช้งานได้ใน baseline mode
- layer-filtered search ฝั่ง API ใช้งานได้แล้ว

#### 2.2 Procedural Memory

Synapse เก็บความรู้เชิงขั้นตอน เช่น:

- วิธีทำงาน
- workflow
- playbook
- step-by-step instruction
- สิ่งที่ผู้ใช้หรือ agent ทำซ้ำบ่อย

รองรับ:

- create/list/get/update/delete procedure
- mark procedure success
- search ขั้นตอนที่เกี่ยวข้องกับคำถาม

#### 2.3 Episodic Memory

Synapse เก็บเหตุการณ์หรือประสบการณ์ที่มีลำดับเวลา เช่น:

- เกิดอะไรขึ้น
- คุยอะไรไป
- สรุป session
- เหตุการณ์ที่สัมพันธ์กับเวลา

รองรับ:

- create episode ผ่าน memory API
- list/get/delete episodes ผ่าน episodes API
- search episode ตามเนื้อหา

#### 2.4 Semantic Memory

Synapse มี semantic layer สำหรับ facts, concepts, meanings, and relationships โดยต่อกับ backend ขั้นสูงได้ เช่น:

- vector similarity ผ่าน `Qdrant`
- graph-backed representation ผ่าน `Graphiti/FalkorDB`

สถานะปัจจุบัน:

- มีโครงสำหรับ semantic retrieval
- มี semantic add/search path
- เหมาะกับ mode ที่เปิด graph/vector backend
- ใน safe baseline mode ระบบยังทำงานได้แม้ semantic backend จะปิด

#### 2.5 Identity and Preferences

Synapse สามารถเก็บข้อมูลตัวตนและ preference ของผู้ใช้ เช่น:

- ชื่อหรือข้อมูล profile
- response style
- response length
- preference อื่นที่ใช้เป็น user context

รองรับ:

- get/update/delete identity
- get/update preferences

#### 2.6 Feed and Activity Stream

Synapse มี feed สำหรับดู event stream ของระบบ:

- event history
- stream แบบ SSE
- ใช้ดูการเปลี่ยนแปลงหรือ activity ของ memory system

ตอนนี้มีการ normalize timestamp ให้ปลอดภัยขึ้นในการ sort และ feed route ใช้งานได้เสถียรกว่าเดิม

#### 2.7 Graph Inspection and System Operations

Synapse รองรับ:

- ตรวจ node และ edge ใน graph
- ดู system status
- ดู stats
- รัน maintenance actions
- clear graph ใน mode ที่ backend graph พร้อม

ถ้า graph driver ไม่พร้อม ระบบจะตอบ `503` แทน success ปลอม

#### 2.8 Oracle-style Interfaces

ยังมี API ที่เน้น orchestration/analysis เช่น:

- `consult`
- `reflect`
- `analyze`

สิ่งเหล่านี้ทำให้ Synapse ไม่ได้เป็นแค่ storage แต่เริ่มมีชั้น reasoning-support สำหรับ agent workflow

### EN

Based on the current API surface and layer manager behavior, Synapse can already do the following:

#### 2.1 Memory CRUD

- add memory via `POST /api/memory`
- list memories via `GET /api/memory`
- retrieve a single memory via `GET /api/memory/{id}`
- search memories via `POST /api/memory/search`
- update a memory via `PUT /api/memory/{id}`
- delete a memory via `DELETE /api/memory/{id}`
- consolidate memory via `POST /api/memory/consolidate`

What is materially working now:

- `request.layer` can override classifier-based routing
- create/update responses now reflect persisted state more reliably
- procedural and episodic CRUD work in baseline mode
- layer-filtered API search works

#### 2.2 Procedural Memory

Synapse stores step-oriented knowledge such as:

- how-to patterns
- workflows
- playbooks
- step-by-step instructions
- repeated user or agent behaviors

It supports:

- create/list/get/update/delete procedure
- mark procedure success
- search for relevant procedures

#### 2.3 Episodic Memory

Synapse stores time-oriented experiences such as:

- what happened
- what was discussed
- session summaries
- time-linked events

It supports:

- episode creation through the memory API
- list/get/delete episodes through the episodes API
- content-based episode search

#### 2.4 Semantic Memory

Synapse includes a semantic layer for facts, concepts, meanings, and relationships, backed by advanced services when available:

- vector similarity via `Qdrant`
- graph-backed representation via `Graphiti/FalkorDB`

Current status:

- the semantic retrieval path exists
- there are semantic add/search flows
- it is best suited to environments where graph/vector backends are enabled
- in safe baseline mode, the system still works even when semantic backends are disabled

#### 2.5 Identity and Preferences

Synapse can store user identity and preference data such as:

- profile-like information
- response style
- response length
- other preference fields used as user context

It supports:

- get/update/delete identity
- get/update preferences

#### 2.6 Feed and Activity Stream

Synapse exposes a feed for system activity:

- event history
- SSE streaming
- visibility into memory system activity

Timestamp normalization has been hardened so feed sorting is more stable and less error-prone than before.

#### 2.7 Graph Inspection and System Operations

Synapse supports:

- graph node and edge inspection
- system status
- system stats
- maintenance actions
- graph clearing when graph backend support exists

When the graph driver is unavailable, the API now returns `503` instead of fake success.

#### 2.8 Oracle-style Interfaces

There are also orchestration-oriented APIs such as:

- `consult`
- `reflect`
- `analyze`

These are important because they position Synapse as more than storage. They move it toward reasoning support for agent workflows.

---

## 3. Memory Model / โมเดลความจำ

### TH

Synapse ใช้แนวคิด memory หลาย layer เพื่อแยก "ชนิดของความรู้" ไม่ให้ทุกอย่างไปกองรวมกันใน vector index เดียว

memory layers ที่สำคัญ:

- `Working`
  สำหรับบริบทชั่วคราวใน session ปัจจุบัน
- `Episodic`
  สำหรับสิ่งที่เกิดขึ้นตามเหตุการณ์และเวลา
- `Semantic`
  สำหรับ facts, concepts, beliefs, meanings, relationships
- `Procedural`
  สำหรับวิธีทำงาน ขั้นตอน หรือ workflow
- `User Model / Identity`
  สำหรับ preference, style, profile-like information

ข้อดีของโมเดลนี้:

- query ที่ต้องการ "วิธีทำ" ไม่ควรปนกับ query ที่ต้องการ "สิ่งที่เคยเกิดขึ้น"
- query ที่ต้องการ user preference ไม่ควรไปค้น episode ทั้งก้อน
- ช่วยให้ routing, search, decay, ranking, maintenance มีโครงสร้างที่ดีขึ้น

### EN

Synapse uses a layered memory model so that different knowledge types are not collapsed into a single undifferentiated vector index.

Key memory layers:

- `Working`
  temporary session context
- `Episodic`
  event- and time-oriented memory
- `Semantic`
  facts, concepts, meanings, beliefs, relationships
- `Procedural`
  how-to knowledge, instructions, workflows
- `User Model / Identity`
  preferences, style, and profile-like context

Why this matters:

- a "how do I do this?" query should not be treated the same as "what happened last week?"
- a preference lookup should not require scanning full episodes
- routing, search, decay, ranking, and maintenance become much more structured

---

## 4. System Flow Today / Flow ของระบบปัจจุบัน

### TH

ภาพรวมของ flow ปัจจุบัน:

```text
Client / Agent
    ->
FastAPI API Layer
    ->
SynapseService
    ->
LayerManager
    ->
Specific Memory Layer
    ->
Durable Store / Derived Indexes
```

รายละเอียดในแต่ละส่วน:

#### 4.1 Ingestion Flow

```text
User or Agent sends data
    ->
API validates request
    ->
Service decides target layer
    ->
Layer-specific write happens
    ->
SQLite persists baseline record
    ->
Optional vector/graph indexing happens
    ->
Response returns persisted state
```

สิ่งสำคัญของ design ปัจจุบัน:

- `SQLite` ต้องเป็น baseline ที่เชื่อถือได้
- vector/graph indexing ไม่ควรทำให้ core write path พัง
- safe mode สามารถปิด graph/vector ได้ด้วย env flags

#### 4.2 Search Flow

```text
User query
    ->
POST /api/memory/search
    ->
SynapseService.search_memory()
    ->
LayerManager.search_all()
    ->
Search selected layers
    ->
Return merged results
```

สำหรับ `procedural` และ `episodic` ปัจจุบัน flow เป็นแบบนี้:

```text
Query
    ->
Vector search in Qdrant
    ->
If empty or unavailable
    ->
SQLite FTS5 search
    ->
If still empty
    ->
SQLite LIKE fallback
```

สำหรับ `semantic`:

```text
Query
    ->
Vector search
    ->
Optional graph-backed retrieval
    ->
Return candidates
```

ข้อควรเข้าใจ:

- นี่คือ hybrid retrieval ในเชิง architecture
- แต่ยังไม่ใช่ full fused ranking ระหว่าง lexical + vector + graph

#### 4.3 Feed Flow

```text
Write / update / delete event
    ->
Event stream / event bus
    ->
Feed API
    ->
History response or SSE stream
```

feed นี้สำคัญสำหรับ:

- debugging
- observability
- audit trail ระดับแอปพลิเคชัน
- integration กับ agent runtime

#### 4.4 Procedure Lifecycle

```text
Procedure created
    ->
Stored durably
    ->
Indexed for search
    ->
Retrieved during relevant tasks
    ->
Marked successful when reused
    ->
Can later be improved or consolidated
```

### EN

The current high-level system flow looks like this:

```text
Client / Agent
    ->
FastAPI API Layer
    ->
SynapseService
    ->
LayerManager
    ->
Specific Memory Layer
    ->
Durable Store / Derived Indexes
```

Details by stage:

#### 4.1 Ingestion Flow

```text
User or Agent sends data
    ->
API validates request
    ->
Service decides target layer
    ->
Layer-specific write happens
    ->
SQLite persists baseline record
    ->
Optional vector/graph indexing happens
    ->
Response returns persisted state
```

Important current design properties:

- `SQLite` is expected to remain the reliable baseline
- vector/graph indexing should not break the core write path
- safe mode can disable graph/vector through environment flags

#### 4.2 Search Flow

```text
User query
    ->
POST /api/memory/search
    ->
SynapseService.search_memory()
    ->
LayerManager.search_all()
    ->
Search selected layers
    ->
Return merged results
```

For `procedural` and `episodic`, the current flow is:

```text
Query
    ->
Vector search in Qdrant
    ->
If empty or unavailable
    ->
SQLite FTS5 search
    ->
If still empty
    ->
SQLite LIKE fallback
```

For `semantic`:

```text
Query
    ->
Vector search
    ->
Optional graph-backed retrieval
    ->
Return candidates
```

What this means:

- this is hybrid retrieval at the architecture level
- but it is not yet full fused ranking across lexical + vector + graph

#### 4.3 Feed Flow

```text
Write / update / delete event
    ->
Event stream / event bus
    ->
Feed API
    ->
History response or SSE stream
```

This feed matters for:

- debugging
- observability
- application-level auditability
- integration with agent runtimes

#### 4.4 Procedure Lifecycle

```text
Procedure created
    ->
Stored durably
    ->
Indexed for search
    ->
Retrieved during relevant tasks
    ->
Marked successful when reused
    ->
Can later be improved or consolidated
```

---

## 5. Deployment Modes / โหมดการใช้งาน

### TH

Synapse ไม่ได้มีโหมดเดียว แต่มีหลายระดับการใช้งานตาม backend ที่เปิด

#### 5.1 Baseline Mode

โหมดนี้ใช้:

- `SQLite`
- `FTS5`
- API core flows

อาจปิด:

- `Qdrant`
- `Graphiti`

เหมาะสำหรับ:

- local development
- safe-mode production baseline
- smoke verification
- environment ที่ต้องการ reliability ก่อน capability

จุดเด่น:

- เสถียร
- start ง่าย
- dependency น้อย
- core memory CRUD ใช้งานได้

#### 5.2 Hybrid Retrieval Mode

โหมดนี้ใช้:

- `SQLite`
- `FTS5`
- `Qdrant`
- optional graph backend

เหมาะสำหรับ:

- semantic similarity
- better recall for concept-like queries
- cross-record retrieval ที่ยืดหยุ่นขึ้น

#### 5.3 Full Context Brain Direction

โหมดนี้ยังเป็นเป้าหมายมากกว่าสถานะปัจจุบัน และจะรวม:

- lexical retrieval
- vector retrieval
- graph traversal
- fused ranking
- reranking
- context compiler
- reflection/consolidation loop

### EN

Synapse is not limited to one deployment mode. It operates across multiple capability tiers depending on enabled backends.

#### 5.1 Baseline Mode

This mode relies on:

- `SQLite`
- `FTS5`
- core API flows

It may disable:

- `Qdrant`
- `Graphiti`

It is suitable for:

- local development
- safe production baseline
- smoke verification
- environments where reliability matters more than advanced retrieval

Its strengths:

- stable
- simple startup
- fewer dependencies
- working core memory CRUD

#### 5.2 Hybrid Retrieval Mode

This mode uses:

- `SQLite`
- `FTS5`
- `Qdrant`
- optional graph backend

It is suited for:

- semantic similarity
- better recall for concept-like queries
- more flexible cross-record retrieval

#### 5.3 Full Context Brain Direction

This is still more of a target architecture than a fully realized state. It would combine:

- lexical retrieval
- vector retrieval
- graph traversal
- fused ranking
- reranking
- context compilation
- reflection/consolidation loops

---

## 6. Why Synapse Is Better Than Simpler Alternatives / Synapse ดีกว่าแนวทางที่ง่ายกว่ายังไง

### TH

คำว่า "ดีกว่า" ในที่นี้ไม่ได้หมายถึงชนะทุกระบบในทุก use case แต่หมายถึง Synapse มีคุณสมบัติบางอย่างที่ระบบ memory แบบง่ายกว่ามักไม่มี

#### 6.1 ดีกว่า chat history อย่างเดียว

ระบบที่ใช้แค่ chat history มักมีปัญหา:

- หาของเก่ายาก
- แยกไม่ได้ว่าอะไรคือ fact, preference, procedure, episode
- scale ไม่ดีเมื่อ session ยาวขึ้น
- ไม่มี memory lifecycle ที่ชัดเจน

Synapse ดีกว่าเพราะ:

- มี memory types หลายแบบ
- มี API CRUD และ search ที่ชัดเจน
- แยก identity, procedures, episodes, semantic knowledge
- รองรับ long-term persistence

#### 6.2 ดีกว่า vector DB อย่างเดียว

ระบบที่มีแต่ vector search มักเจอปัญหา:

- ทุกอย่างกลายเป็น embedding
- exact match บางอย่างกลับหาไม่เจอ
- update/delete/control ยาก
- อธิบาย provenance หรือ lifecycle ได้ยาก

Synapse ดีกว่าเพราะ:

- มี `SQLite` เป็น source-of-truth baseline
- มี lexical fallback
- มี structured objects เช่น procedures, identity, episodes
- ไม่ผูกชีวิตทั้งระบบกับ vector backend ตัวเดียว

#### 6.3 ดีกว่า RAG document store ทั่วไป

RAG ทั่วไปมักเน้น:

- chunk documents
- embed chunks
- retrieve top-k

แต่สำหรับ Personal AI นั่นยังไม่พอ เพราะ Personal AI ต้องจำ:

- ผู้ใช้ชอบอะไร
- เคยทำอะไร
- ทำงานอย่างไร
- โปรเจคไหนสำคัญ
- เรื่องไหนยังค้าง

Synapse ดีกว่าเพราะเริ่มออกแบบเป็น personal memory runtime ไม่ใช่ document retriever อย่างเดียว

#### 6.4 ดีกว่า graph-only หรือ vector-only แบบสุดโต่ง

graph-only มักแข็งแรงเรื่อง relation แต่ไม่เก่ง recall แบบ fuzzy semantic search  
vector-only มักเก่ง semantic similarity แต่ไม่เก่ง structure, provenance, and exact control

Synapse พยายามเก็บข้อดีของหลายแบบ:

- durable store
- lexical retrieval
- vector retrieval
- graph representation
- typed memory

แม้ตอนนี้ยังไม่ fuse ได้เต็มรูป แต่ทิศทาง architecture ถูกต้องกว่าการเลือก backend เดียวให้ทำทุกอย่าง

### EN

"Better" does not mean better than every system in every use case. It means Synapse has important properties that simpler memory systems usually lack.

#### 6.1 Better than chat history alone

Chat-history-only systems often struggle with:

- poor retrieval of old information
- no distinction between facts, preferences, procedures, and episodes
- poor scaling as sessions grow longer
- no explicit memory lifecycle

Synapse improves on that by providing:

- multiple memory types
- explicit CRUD and search APIs
- separation of identity, procedures, episodes, and semantic knowledge
- durable long-term persistence

#### 6.2 Better than a vector DB alone

Vector-only systems often suffer from:

- everything being forced into embeddings
- poor exact matching in some cases
- weak update/delete/control semantics
- weak provenance and lifecycle modeling

Synapse improves on that because:

- `SQLite` remains the source-of-truth baseline
- lexical fallback exists
- structured objects exist, such as procedures, identity, and episodes
- the entire system is not held hostage by a single vector backend

#### 6.3 Better than generic RAG document stores

Generic RAG systems usually focus on:

- chunk documents
- embed chunks
- retrieve top-k

For Personal AI, that is not enough. Personal AI must remember:

- what the user prefers
- what has happened before
- how work gets done
- which projects matter
- what remains unresolved

Synapse is stronger here because it is designed as a personal memory runtime, not just a document retriever.

#### 6.4 Better than extreme graph-only or vector-only designs

Graph-only systems are often strong at relations but weaker at fuzzy semantic recall.  
Vector-only systems are often strong at semantic similarity but weaker at structure, provenance, and exact operational control.

Synapse tries to combine the strengths of multiple approaches:

- durable storage
- lexical retrieval
- vector retrieval
- graph representation
- typed memory

It does not fully fuse them yet, but the architecture direction is stronger than forcing one backend to do everything.

---

## 7. Current Strengths / จุดแข็งปัจจุบัน

### TH

จุดแข็งของ Synapse ณ ตอนนี้:

- มี API surface ค่อนข้างครบสำหรับ memory system ขนาดจริง
- baseline mode ใช้งานได้จริงโดยไม่ต้องพึ่ง graph/vector
- CRUD หลักของ procedural และ episodic ใช้งานได้
- มี feed และ observability flow ระดับหนึ่ง
- มี identity/preferences สำหรับ personal context
- มี route/system operations สำหรับ maintenance และ stats
- มีโครง semantic + graph ที่ต่อยอดได้
- มี smoke script และ release checklist สำหรับ deployment discipline

### EN

Current strengths of Synapse:

- a relatively broad API surface for a real memory system
- a working baseline mode that does not depend on graph/vector services
- working core CRUD for procedural and episodic memory
- feed and activity visibility
- identity/preferences support for personal context
- system routes for maintenance and stats
- a semantic + graph foundation that can be extended
- smoke scripts and release checklist discipline for deployment

---

## 8. Current Limitations / ข้อจำกัดปัจจุบัน

### TH

ข้อจำกัดที่ต้องพูดตรง ๆ:

- ยังไม่ใช่ `true hybrid search` แบบมี score fusion เต็มรูป
- semantic quality ยังขึ้นกับ backend availability
- graph mode ยังไม่ใช่ fully verified universal production path ทุก environment
- ยังไม่มี `context compiler` ที่คัดเลือก context ให้ model อย่างเป็นระบบ
- ยังไม่มี `goals/projects/relationship intelligence` ในระดับที่สมบูรณ์
- reflective maintenance, contradiction resolution, and long-horizon summarization ยังอยู่ในระดับต้น
- trust/privacy controls แบบละเอียด เช่น explainability, redaction, consent scopes ยังไม่ครบ

### EN

Important current limitations:

- it is not yet a `true hybrid search` system with full score fusion
- semantic quality still depends on backend availability
- graph mode is not yet a universally verified production path across all environments
- there is no complete `context compiler` yet
- goals, projects, and relationship intelligence are not yet fully developed
- reflective maintenance, contradiction resolution, and long-horizon summarization are still early
- fine-grained trust/privacy controls such as explainability, redaction, and consent scopes are incomplete

---

## 9. Current Verified Level / ระดับที่ยืนยันได้ตอนนี้

### TH

หากอิงจากงาน hardening และ smoke verification ล่าสุด ควรอธิบายสถานะระบบแบบ conservative ดังนี้:

- `SQLite baseline memory runtime`: ใช้งานได้จริง
- `Core API memory flows`: ใช้งานได้จริง
- `Procedural + episodic lifecycle`: ใช้งานได้ในระดับใช้งานจริง
- `Feed / auth / maintenance baseline`: ใช้งานได้จริง
- `Hybrid graph/vector mode`: ใช้งานได้บาง environment แต่ยังต้อง verify ต่อเนื่อง
- `True personal brain behavior`: ยังไม่ถึง

ประโยคที่อธิบายระบบได้ตรงที่สุดตอนนี้คือ:

> Synapse is a reliable baseline personal memory runtime with layered memory, API-driven lifecycle control, and optional hybrid retrieval backends.

### EN

Based on the latest hardening and smoke verification work, the most conservative and accurate description is:

- `SQLite baseline memory runtime`: working
- `Core API memory flows`: working
- `Procedural + episodic lifecycle`: practically usable
- `Feed / auth / maintenance baseline`: working
- `Hybrid graph/vector mode`: works in some environments but still needs ongoing verification
- `True personal brain behavior`: not there yet

The most accurate one-line description today is:

> Synapse is a reliable baseline personal memory runtime with layered memory, API-driven lifecycle control, and optional hybrid retrieval backends.

---

## 10. Ideal Future Flow / Flow ที่ควรเป็นในอนาคต

### TH

เป้าหมายระยะกลางถึงยาวควรเป็น flow แบบนี้:

```text
Raw event ingestion
    ->
Normalization and provenance
    ->
Episode / fact / entity / procedure extraction
    ->
Durable record write
    ->
Lexical + vector + graph indexing
    ->
Parallel retrieval at query time
    ->
Score fusion + reranking
    ->
Context compiler
    ->
LLM / Agent execution
    ->
Reflection and consolidation
```

นี่คือจุดที่ Synapse จะก้าวจาก memory service ไปเป็น `Personal Brain Runtime`

### EN

The mid- to long-term target flow should look like this:

```text
Raw event ingestion
    ->
Normalization and provenance
    ->
Episode / fact / entity / procedure extraction
    ->
Durable record write
    ->
Lexical + vector + graph indexing
    ->
Parallel retrieval at query time
    ->
Score fusion + reranking
    ->
Context compiler
    ->
LLM / Agent execution
    ->
Reflection and consolidation
```

That is the point at which Synapse moves from a memory service to a true `Personal Brain Runtime`.

---

## 11. Bottom Line / บทสรุปสุดท้าย

### TH

Synapse ในวันนี้ดีกว่าระบบ memory ที่มีแค่ chat history, vector DB, หรือ generic RAG แบบตรงไปตรงมา เพราะมันมี:

- layered memory
- durable baseline
- CRUD lifecycle
- feed and maintenance
- identity and personal context
- optional hybrid backends

แต่ถ้าจะให้เป็น "สมองที่ดีที่สุดสำหรับ Personal AI" จริง ยังต้องเพิ่ม:

- true hybrid ranking
- context compiler
- personal goals/projects/relationship model
- reflection and consolidation engine
- privacy/trust controls ที่ละเอียด

ดังนั้นคำอธิบายที่ถูกต้องที่สุดตอนนี้คือ:

`Synapse เป็น personal memory runtime ที่ foundation ดีและมีทิศทางถูกต้องมาก แต่ยังอยู่ระหว่างการพัฒนาไปสู่ personal brain เต็มรูป`

### EN

Today, Synapse is stronger than a plain chat-history system, a vector DB by itself, or a generic RAG store because it already provides:

- layered memory
- a durable baseline
- CRUD lifecycle support
- feed and maintenance flows
- identity and personal context
- optional hybrid backends

But to become "the best brain for Personal AI", it still needs:

- true hybrid ranking
- a context compiler
- personal goals/projects/relationship models
- a reflection and consolidation engine
- richer privacy/trust controls

The most accurate summary today is:

`Synapse is a strong personal memory runtime foundation with the right direction, but it is still evolving toward a full personal brain.`
