# Synapse Personal Brain Architecture and Maturity Plan

Review date: 2026-03-21
Owner perspective: Lead Context Engineering
Scope: product direction, target architecture, current maturity, execution plan

## Executive Summary

If Synapse is meant to become the best brain for Personal AI, it should not be treated as "just a memory API" or "just a RAG stack".

It should become a `Personal Context OS` with three clear layers:

- `Truth Layer`: durable raw events and user-owned records
- `Knowledge Layer`: extracted episodes, facts, entities, relations, procedures, preferences, goals
- `Context Layer`: query-time selection, ranking, compression, and packaging of the most useful context for the current task

Current state:

- `SQLite baseline mode`: usable and increasingly reliable
- `Hybrid retrieval`: partially implemented
- `True hybrid ranking`: not implemented yet
- `Context compiler`: not implemented yet
- `Reflective personal brain`: still early

Current maturity verdict:

- `Overall`: Level 2 of 5
- `SQLite-only baseline`: Level 2
- `Hybrid graph/vector mode`: Level 1 to 2, depending on environment

That means Synapse is now moving from `prototype memory service` toward `reliable memory runtime`, but it is not yet a full personal brain.

---

## North Star

Synapse should become the long-term memory and context runtime for all of a user's AI agents.

The ideal system should:

- remember what happened
- know what is true, uncertain, stale, or superseded
- know what matters to this user
- know what procedure to reuse
- know what project, goal, and person a request belongs to
- compile the right context for the current task under a strict token budget
- explain why a memory was used
- safely forget, redact, export, and rebuild memory

In short:

```text
Synapse = Personal Brain Runtime
not
Synapse = vector DB + graph DB + CRUD API
```

---

## Design Principles

### 1. Truth before indexes

`SQLite` or another durable local store must be the source of truth.

- Qdrant is an index
- Graphiti/FalkorDB is an index and relationship engine
- FTS is an index
- summaries are derived artifacts

The system must remain useful even when derived indexes are degraded or disabled.

### 2. Retrieval is not context

Finding records is only step one.
The actual product value comes from selecting and packaging the right context for the model at query-time.

### 3. Personal memory needs provenance

Every meaningful record should carry:

- source
- actor
- timestamp
- scope
- confidence
- consent / privacy class
- superseded / archived state

### 4. Memory must be multi-timescale

The system must distinguish:

- current task context
- recent session memory
- episodic timeline memory
- stable semantic knowledge
- persistent user model
- procedures and habits
- long-term goals and projects

### 5. The system must explain itself

The user should be able to ask:

- why do you remember this?
- where did this fact come from?
- how confident are you?
- forget this
- show me what you know about X

---

## Target Architecture

## 1. Truth Layer

This is the durable substrate.

Primary records:

- raw events
- chats
- user edits
- notes
- file observations
- browser/app actions
- calendar/task signals
- explicit user saves

Key requirement:

- append-only event journal
- immutable record IDs
- rebuildable indexes

## 2. Knowledge Layer

This is where the system turns raw activity into useful memory objects.

Core domain objects:

- `Episode`
- `Fact`
- `Entity`
- `Relation`
- `Procedure`
- `Preference`
- `Goal`
- `Project`
- `WorkingContext`
- `Summary`

Key requirement:

- knowledge objects are durable records, not only embeddings

## 3. Context Layer

This is the real "brain" behavior.

Core components:

- request analyzer
- retrieval planner
- candidate fetchers
- hybrid ranking engine
- reranker
- context packager
- uncertainty and contradiction filter

Key requirement:

- the model sees curated context, not raw search dumps

---

## End-to-End Flow

### A. Ingestion Flow

```text
User / App / File / Calendar / Browser / Agent Event
    ->
Normalize event
    ->
Attach identity, timestamp, source, scope, provenance
    ->
Write raw event journal
    ->
Emit indexing and extraction jobs
```

### B. Understanding Flow

```text
Raw event
    ->
Classify event type
    ->
Extract:
- episode
- fact
- entity
- procedure
- preference
- goal/project signal
    ->
Write durable knowledge objects
    ->
Mark indexing state
```

### C. Indexing Flow

```text
Durable knowledge object
    ->
Lexical index (FTS/BM25)
    ->
Vector index
    ->
Graph index
    ->
Summaries / caches / denormalized views
```

### D. Query-Time Context Flow

```text
User request
    ->
Request analyzer
    ->
Task mode selection
    ->
Retrieval plan
    ->
Candidate fetch from:
- working context
- recent session
- episodic
- procedural
- semantic
- user model
- goals/projects
- graph
    ->
Hybrid score fusion
    ->
Reranking
    ->
Context packaging under token budget
    ->
LLM answer / action
```

### E. Reflection Flow

```text
Completed interaction / task outcome
    ->
Observe success/failure
    ->
Update access and confidence
    ->
Promote repeated patterns into procedures
    ->
Supersede stale facts
    ->
Compress older episodes into summaries
    ->
Refresh user model, project state, and goals
```

---

## Maturity Model

| Level | Name | Meaning |
|---|---|---|
| L0 | Fragmented Prototype | CRUD exists, but durability and retrieval are not trustworthy |
| L1 | Memory Service | Basic storage and search work in isolated cases |
| L2 | Reliable Memory Runtime | Durable baseline works, fallbacks exist, release gates exist |
| L3 | Hybrid Context Platform | Parallel retrieval, fusion, reranking, and mode-aware context assembly |
| L4 | Personal Context OS | Goals, projects, life graph, reflection, and multi-agent continuity |
| L5 | Reflective Personal Brain | Self-maintaining, explainable, trusted, and measurably strong over long horizons |

---

## Current Maturity Assessment

## Overall Rating

`Current overall maturity: L2`

Interpretation:

- good enough to behave like a `reliable memory runtime` in baseline mode
- not yet good enough to behave like a `true personal brain`

## Current Verified Facts

As of this review:

- auth enforcement exists
- memory/procedure/preferences/feed/system flows pass the current safe smoke gate
- safe smoke gate passes in `SQLite-only baseline mode`
- search fallback now works when vector search returns no results
- graph and qdrant can be explicitly disabled by environment flags

Known verified baseline command:

```bash
SYNAPSE_ENABLE_GRAPHITI=false SYNAPSE_ENABLE_QDRANT=false \
python scripts/pre_deploy_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --api-key "$SYNAPSE_API_KEY" \
  --output-json artifacts/pre_deploy_smoke.sqlite_only.json
```

## Maturity by Subsystem

| Subsystem | Current Level | Status | Notes |
|---|---|---|---|
| Durable baseline storage | L2 | Strongest area | SQLite-backed flows now behave reliably |
| API contracts and CRUD | L2 | Good | core responses and basic flows are much better than before |
| Release gate / smoke verification | L2 | Good | checklist and smoke script now exist and were exercised |
| Episodic retrieval | L2 | Good baseline | vector + lexical fallback works |
| Procedural retrieval | L2 | Good baseline | vector + lexical fallback works |
| Semantic retrieval | L1 | Partial | vector and graph exist, but no fused ranking |
| Hybrid search engine | L1 | Weak | retrieval sources exist, fusion does not |
| Context compiler | L0 | Missing | no dedicated retrieval planner / packager |
| Reflection and consolidation | L1 | Early | partial behavior exists, not yet systematized |
| User model / personalization | L1 | Early | preferences exist, but goals/projects are missing |
| Trust / privacy / control | L0 | Missing | no robust consent, redaction, export, or explainability model |
| Observability / evaluation | L0 | Missing | no formal retrieval quality metrics |
| Multi-agent shared brain | L1 | Early | IDs/scopes exist, but no mature cross-agent memory policy |

## Practical Meaning of Current State

Synapse can currently do these things reasonably well:

- persist and retrieve baseline episodic/procedural memory
- survive graph/vector outages in baseline mode
- expose a usable API surface for core memory operations
- run a release smoke gate for baseline production checks

Synapse cannot yet do these things at "best brain" level:

- compile optimal context for a task
- unify lexical, vector, and graph search into one ranked answer set
- maintain long-term goals, projects, and relationship memory in a coherent way
- explain memory provenance and confidence in a rigorous way
- continuously reflect, compress, and improve its own memory graph

---

## Gap Analysis

## 1. No raw event journal

Current:

- writes go directly into layer-specific durable objects

Missing:

- append-only canonical event log
- replay-based rebuild
- durable provenance chain

Impact:

- rebuild and forensic reasoning are weaker than they should be

## 2. Retrieval exists, but fusion does not

Current:

- procedural and episodic perform vector-first retrieval and lexical fallback
- semantic performs vector retrieval and optional graph search

Missing:

- unified candidate schema
- parallel retrieval across all backends
- score fusion
- reranking

Impact:

- quality is highly backend-dependent
- retrieval is not yet globally optimized

## 3. No context compiler

Current:

- system can search and return results

Missing:

- request analyzer
- retrieval planner
- token budget allocator
- must-have vs nice-to-have context packaging

Impact:

- memory can be found, but not yet shaped optimally for model reasoning

## 4. Personal intelligence is shallow

Current:

- identity and preferences exist

Missing:

- goals
- projects
- life timeline
- relationship state
- unresolved thread tracking
- habit extraction

Impact:

- system remembers facts, but does not yet understand the user's life and work deeply

## 5. Reflection is incomplete

Current:

- some maintenance and consolidation concepts exist

Missing:

- routine promotion of repeated behavior into procedures
- contradiction detection
- stale fact supersession policy across all layers
- long-horizon summarization

Impact:

- memory quality will decay over time even if storage remains available

## 6. Trust and governance are immature

Current:

- basic auth exists

Missing:

- privacy classes
- per-source consent
- export/delete/explain controls
- retention and redaction policy

Impact:

- not yet safe enough for long-term personal use at scale

---

## Recommended Architecture Shape

The best version of Synapse should be organized around these runtime components:

### 1. Event Journal

Responsibilities:

- append-only raw event log
- canonical source of truth
- replay into derived stores

### 2. Knowledge Extractor

Responsibilities:

- classify raw events
- extract facts, episodes, entities, procedures, preferences, goals
- assign confidence and provenance

### 3. Index Builder

Responsibilities:

- build lexical, vector, and graph indexes
- track indexing state per record
- reindex and repair

### 4. Hybrid Retrieval Engine

Responsibilities:

- run lexical, vector, graph, and metadata retrieval in parallel
- normalize candidate scores
- fuse and rerank candidates

### 5. Context Compiler

Responsibilities:

- understand task type
- fetch the right classes of memory
- compress results under token budget
- emit grounded context blocks

### 6. Reflection Engine

Responsibilities:

- consolidate
- promote
- supersede
- summarize
- archive

### 7. Trust and Governance Layer

Responsibilities:

- privacy
- deletion
- export
- provenance
- explanation

---

## Execution Roadmap

## Phase 1: Brain Substrate

Goal:

- make memory durable, replayable, and auditable

Deliverables:

- raw event journal
- record provenance schema
- indexing state per record
- replay/rebuild tooling

Key schema additions:

- `event_id`
- `record_id`
- `source_type`
- `source_ref`
- `actor_id`
- `scope`
- `confidence`
- `index_status_vector`
- `index_status_graph`
- `superseded_by`

Exit criteria:

- every derived object can be traced back to raw input
- indexes can be rebuilt from truth storage

## Phase 2: True Hybrid Retrieval

Goal:

- turn fallback search into production hybrid search

Deliverables:

- semantic lexical index
- parallel retrieval execution
- unified candidate schema
- score fusion engine
- reranker

Recommended first fusion strategy:

- `RRF` for simplicity and robustness

Recommended scoring dimensions:

- lexical relevance
- vector similarity
- graph proximity
- freshness
- confidence
- personalization

Exit criteria:

- top-k quality is no longer dependent on one backend
- retrieval remains useful even when one backend is degraded

## Phase 3: Context Compiler

Goal:

- convert retrieval into model-ready context

Deliverables:

- request analyzer
- retrieval planner
- context budget allocator
- context packager
- uncertainty and contradiction annotations

Modes to support:

- quick answer
- deep reasoning
- coding
- planning
- recall
- agent action

Exit criteria:

- the system can explain why a given memory was included
- context quality is measurably better than raw search dumps

## Phase 4: Personal Model Expansion

Goal:

- make the system truly personal

Deliverables:

- goals
- projects
- people graph
- relationship memory
- life timeline
- unresolved thread tracking
- habit and routine extraction

Exit criteria:

- the system can answer not only "what happened?" but also "what matters to this person?"

## Phase 5: Reflection and Long-Horizon Maintenance

Goal:

- make the brain improve itself over time

Deliverables:

- repeated pattern detection
- automatic procedure promotion
- contradiction detection
- stale fact supersession
- episode compression and summarization
- archive policies

Exit criteria:

- memory quality improves or stays stable over time instead of drifting downward

## Phase 6: Trust, Privacy, and Multi-Agent Brain

Goal:

- make the system safe and usable for long-term real-life operation

Deliverables:

- consent classes
- memory visibility and scoping
- redaction and delete
- export and explain endpoints
- shared-brain policy for multiple agents
- role-aware context boundaries

Exit criteria:

- the user can trust the brain with real personal and project data

---

## Near-Term Priorities

If execution starts now, the next steps should be:

### Immediate

- keep SQLite baseline solid
- stabilize graph/vector full-mode verification
- ensure smoke script supports baseline and full-mode separately
- formalize deploy modes:
  - baseline
  - hybrid
  - full semantic

### Next technical milestone

- implement semantic lexical search
- implement unified candidate schema
- implement parallel retrieval plus RRF fusion

### First major product milestone

- build the first real context compiler:
  - task analyzer
  - retrieval planner
  - prompt packager

---

## Success Metrics

To become the best brain, Synapse needs measurable quality targets.

Recommended metrics:

- Recall@K for episodic, procedural, semantic, and personal queries
- MRR / NDCG for ranked retrieval
- answer grounding rate
- contradiction rate
- stale-context rate
- context token efficiency
- index lag
- p95 retrieval latency
- successful cross-session continuity rate
- procedure reuse rate

---

## Final Position

Synapse today is no longer just a fragile prototype.

In baseline mode it is approaching a reliable memory runtime.

But the target should be much larger:

```text
Current: reliable memory runtime
Next: hybrid retrieval platform
Target: personal context OS
End state: reflective personal brain
```

That is the correct framing if the goal is to build the best brain for Personal AI.
