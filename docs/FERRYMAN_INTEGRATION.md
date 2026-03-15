# Ferryman Integration - Synapse Side

> Memory Layer Requirements for Search System
> Created: 2026-03-15
> Status: Planning

---

## 1. Overview

### Synapse's Role in Search System

Synapse serves as the **Memory Layer** for the search system:

```
┌─────────────────────────────────────────────────────────────┐
│                     SEARCH ECOSYSTEM                         │
│                                                              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐  │
│   │  CERBERUS   │────►│   SYNAPSE   │◄────│  FERRYMAN   │  │
│   │  (Router)   │     │  (Memory)   │     │  (Search)   │  │
│   └─────────────┘     └─────────────┘     └─────────────┘  │
│                              │                              │
│                    ┌─────────┼─────────┐                   │
│                    ▼         ▼         ▼                   │
│              ┌────────┐ ┌────────┐ ┌────────┐              │
│              │FalkorDB│ │ Qdrant │ │SQLite  │              │
│              │(Graph) │ │(Vector)│ │(FTS5)  │              │
│              └────────┘ └────────┘ └────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Key Responsibilities

1. **Store search-derived knowledge** - Important facts from web searches
2. **Freshness tracking** - Know when knowledge is stale
3. **Fast retrieval** - Quick memory checks for router
4. **TTL management** - Automatic expiration of time-sensitive data

---

## 2. Memory Layer Mapping

### Where Search Results Go

```
┌─────────────────────────────────────────────────────────────┐
│                    FIVE-LAYER MEMORY                         │
│                                                              │
│  Layer 1: USER_MODEL (Never decay)                          │
│  ├── User search preferences                                │
│  └── Preferred sources                                      │
│                                                              │
│  Layer 2: PROCEDURAL (Slow decay, λ=0.005)                  │
│  ├── Search procedures                                      │
│  └── Query patterns                                         │
│                                                              │
│  Layer 3: SEMANTIC (Normal decay, λ=0.01) ← MAIN TARGET     │
│  ├── Factual knowledge from web                             │
│  ├── Definitions, concepts                                  │
│  └── Long-lasting information                               │
│                                                              │
│  Layer 4: EPISODIC (TTL 90 days) ← TIME-SENSITIVE TARGET    │
│  ├── News and current events                                │
│  ├── Stock prices, weather data                             │
│  └── Time-bound information                                 │
│                                                              │
│  Layer 5: WORKING (Session only)                            │
│  ├── Current search context                                 │
│  └── Temporary query state                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Content Type → Layer Mapping

| Content Type | Layer | TTL | Decay |
|--------------|-------|-----|-------|
| User preferences | Layer 1 | Never | No |
| Search procedures | Layer 2 | ~139 days | Slow |
| Factual knowledge | Layer 3 | ~69 days | Normal |
| News/Events | Layer 4 | 90 days | TTL |
| Query context | Layer 5 | Session | None |

---

## 3. Required Upgrades

### 3.1 New Entity Types

```python
# synapse/layers/types.py

class WebSource(BaseModel):
    """Source from web search"""
    url: str
    title: str
    site_name: str
    credibility_score: float = 0.7
    last_fetched: datetime

class SearchKnowledge(BaseModel):
    """Knowledge extracted from web search"""
    query: str
    answer: str
    sources: List[WebSource]
    confidence: float
    query_type: QueryType  # realtime, daily, factual, research
    valid_until: Optional[datetime]  # For time-sensitive data
```

### 3.2 Freshness Query Endpoint

```python
# New MCP tool

@mcp.tool()
async def check_knowledge_freshness(
    query: str,
    max_age_hours: int = 24,
    group_ids: list[str] | None = None,
) -> FreshnessResponse:
    """
    Check if we have fresh knowledge for a query.

    Returns:
        - has_knowledge: bool
        - is_fresh: bool
        - age_hours: float | None
        - knowledge_summary: str | None
    """
```

### 3.3 Batch Store for Search Results

```python
@mcp.tool()
async def store_search_knowledge(
    query: str,
    answer: str,
    sources: list[dict],
    query_type: str,  # "realtime" | "daily" | "factual" | "research"
    group_id: str | None = None,
) -> SuccessResponse:
    """
    Store knowledge derived from web search.

    Automatically routes to appropriate layer based on query_type:
    - realtime → Layer 4 with short TTL
    - daily → Layer 4 with medium TTL
    - factual → Layer 3 (semantic)
    - research → Layer 3 (semantic)
    """
```

---

## 4. Synapse Flow

### 4.1 Memory Check Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY CHECK FLOW                         │
│                                                              │
│  Cerberus: "check_knowledge_freshness('BTC price', 1)"      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Vector Search (Qdrant)                           │    │
│  │    query → embedding → search semantic_memory       │    │
│  │    threshold: 0.8                                   │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2. Graph Search (FalkorDB)                          │    │
│  │    MATCH (n) WHERE n.content CONTAINS query         │    │
│  │    AND n.created_at > now - max_age                 │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 3. FTS Search (SQLite)                              │    │
│  │    SELECT * FROM episodic_fts WHERE                 │    │
│  │    content MATCH query AND created_at > threshold   │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 4. Merge & Rank                                     │    │
│  │    Combine results, calculate freshness             │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  Response:                                            │    │
│  {                                                    │    │
│    "has_knowledge": true,                             │    │
│    "is_fresh": false,  // 2 hours old, need 1 hour    │    │
│    "age_hours": 2.0,                                  │    │
│    "knowledge_summary": "BTC was at $95,000..."       │    │
│  }                                                    │    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Store Search Result Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  STORE SEARCH RESULT FLOW                    │
│                                                              │
│  Ferryman: "store_search_knowledge(query, answer, ...)"     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Classify Query Type                              │    │
│  │    query_type = classify(query)                     │    │
│  │    → realtime, daily, factual, research             │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 2. Determine Target Layer                           │    │
│  │    if query_type in [realtime, daily]:              │    │
│  │        layer = EPISODIC with TTL                    │    │
│  │    else:                                            │    │
│  │        layer = SEMANTIC                             │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 3. Extract Entities (LLM)                           │    │
│  │    entities = extract_entities(answer)              │    │
│  │    relationships = extract_relationships(answer)    │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 4. Store in Multiple Backends                       │    │
│  │                                                     │    │
│  │    FalkorDB: entities + relationships               │    │
│  │    Qdrant:   answer embedding (semantic_memory)     │    │
│  │    SQLite:   full episode with metadata             │    │
│  └────────────────────┬────────────────────────────────┘    │
│                       │                                      │
│                       ▼                                      │
│  Response: { "success": true, "episode_id": "..." }         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Synapse Vision Roadmap

### Current State (M1 Complete)

```
✅ Five-Layer Memory Model
✅ Graphiti integration (FalkorDB)
✅ Qdrant vector store
✅ MCP Server (HTTP transport)
✅ Thai NLP tools
✅ Local embedder (multilingual-e5-small)
✅ Ollama LLM support
```

### M2: Claude/Cerberus Integration (Current)

```
⬜ Test MCP with Claude Desktop
⬜ Test MCP with Cerberus
⬜ Document API
⬜ Performance benchmarking
```

### M3: Ferryman Integration (NEW)

```
⬜ 3.1 Freshness Query
    ├── check_knowledge_freshness tool
    ├── Multi-backend search (Graph + Vector + FTS)
    └── Age calculation

⬜ 3.2 Search Knowledge Storage
    ├── store_search_knowledge tool
    ├── Auto layer routing
    └── Source tracking

⬜ 3.3 TTL Management
    ├── Per-content-type TTL
    ├── Automatic expiration
    └── Extension on access

⬜ 3.4 Query Classification
    ├── Query type detection
    ├── Layer routing logic
    └── Freshness thresholds
```

### M4: Production Deployment

```
⬜ Docker Compose for all services
⬜ Health checks
⬜ Backup/restore
⬜ Monitoring & metrics
```

### M5: Advanced Memory

```
⬜ Memory consolidation
⬜ Conflict resolution
⬜ Memory pruning
⬜ Cross-user learning (optional)
```

---

## 6. API Specification

### New MCP Tools

#### check_knowledge_freshness

```python
@mcp.tool()
async def check_knowledge_freshness(
    query: str,
    max_age_hours: int = 24,
    group_ids: list[str] | None = None,
    min_confidence: float = 0.7,
) -> FreshnessResponse | ErrorResponse:
    """
    Check if we have fresh, relevant knowledge for a query.

    Args:
        query: The search query to check
        max_age_hours: Maximum age in hours for knowledge to be fresh
        group_ids: Optional list of group IDs to search
        min_confidence: Minimum confidence threshold

    Returns:
        FreshnessResponse with:
        - has_knowledge: bool
        - is_fresh: bool
        - age_hours: float | None
        - confidence: float
        - knowledge_summary: str | None
        - sources: list[dict] | None
    """
```

#### store_search_knowledge

```python
@mcp.tool()
async def store_search_knowledge(
    query: str,
    answer: str,
    sources: list[dict],
    query_type: str = "factual",  # realtime | daily | factual | research
    group_id: str | None = None,
    confidence: float = 0.8,
) -> SuccessResponse | ErrorResponse:
    """
    Store knowledge derived from web search.

    Args:
        query: Original search query
        answer: The answer/summary from search
        sources: List of source dictionaries with url, title, site_name
        query_type: Type of query (affects TTL and layer)
        group_id: Optional group ID
        confidence: Confidence score for the knowledge

    Returns:
        SuccessResponse with episode_id
    """
```

#### get_layer_stats

```python
@mcp.tool()
async def get_layer_stats(
    group_id: str | None = None,
) -> LayerStatsResponse:
    """
    Get statistics about each memory layer.

    Returns:
        LayerStatsResponse with:
        - layers: dict of layer_name -> stats
        - total_nodes: int
        - total_episodes: int
    """
```

---

## 7. Files to Create/Modify

### New Files

```
synapse/mcp_server/src/
├── search_tools.py        # Search-related MCP tools
├── freshness.py           # Freshness checking logic
├── query_classifier.py    # Query type classification
└── layer_router.py        # Layer routing based on content type
```

### Files to Modify

```
synapse/layers/types.py          # Add WebSource, SearchKnowledge types
synapse/mcp_server/src/
├── graphiti_mcp_server.py       # Register new tools
└── models/response_types.py     # Add FreshnessResponse, etc.
```

---

## 8. Performance Requirements

| Operation | Target Latency | Notes |
|-----------|----------------|-------|
| check_knowledge_freshness | < 100ms | Hot path for router |
| store_search_knowledge | < 500ms | Async processing OK |
| search_nodes | < 200ms | Existing tool |
| search_memory_facts | < 200ms | Existing tool |

### Optimization Strategies

1. **Caching** - Cache frequent queries in memory
2. **Indexing** - Proper indexes on created_at, query_type
3. **Parallel search** - Query Graph + Vector + FTS in parallel
4. **Lazy loading** - Load embeddings only when needed

---

## 9. TTL Configuration

```python
# synapse/layers/types.py

class SearchTTLConfig:
    """TTL configuration for search-derived knowledge"""

    # Realtime data (stock prices, live scores)
    REALTIME_TTL_HOURS = 1

    # Daily data (weather, daily news)
    DAILY_TTL_HOURS = 24

    # Factual data (definitions, concepts)
    FACTUAL_TTL_DAYS = 365  # Essentially permanent

    # Research data (papers, documentation)
    RESEARCH_TTL_DAYS = 180

    # Extension on access
    ACCESS_EXTENSION_HOURS = 6
```

---

## 10. Integration with Ferryman

### Ferryman → Synapse Communication

```
┌─────────────┐                    ┌─────────────┐
│  FERRYMAN   │                    │   SYNAPSE   │
└──────┬──────┘                    └──────┬──────┘
       │                                  │
       │  1. search("BTC price")          │
       │  ──────────────────────────────► │
       │                                  │
       │  2. check_knowledge_freshness()  │
       │  ◄────────────────────────────── │
       │     {is_fresh: false}            │
       │                                  │
       │  3. [Do web search]              │
       │                                  │
       │  4. store_search_knowledge()     │
       │  ──────────────────────────────► │
       │     {success: true}              │
       │                                  │
```

---

## 11. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Freshness check latency | < 100ms | p95 |
| Store latency | < 500ms | p95 |
| Memory hit rate | > 30% | Cache analysis |
| Knowledge accuracy | > 90% | User feedback |

---

## 12. References

- [Cerberus Integration](../cerberus/docs/FERRYMAN_INTEGRATION.md)
- [Synapse Architecture](./ARCHITECTURE.md)
- [Five-Layer Memory Model](./MEMORY_LAYERS.md)
- [Graphiti Documentation](https://github.com/getzep/graphiti)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-15 | Initial planning document |
