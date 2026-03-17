# QA Audit Report — Layer 3 Graph Population

> **Date**: 2026-03-17T12:50+07:00
> **Analyst**: Orga (QA Agent)
> **Focus**: Layer 3 Semantic/Graph Population Verification
> **Severity**: 🔴 CRITICAL

---

## 🎯 Executive Summary

**คำถาม**: "value จริงอยู่ที่ Layer 3 (Semantic/Graph) ถ้า Graph ไม่ถูก populate — ที่เหลืออีก 4 layers ก็เป็นแค่ SQLite + vector store ธรรมดา"

**คำตอบ**: **ใช่ และ Graph ไม่ถูก populate จริง!**

| Metric | Value |
|--------|-------|
| **Quality Score** | 35/100 |
| **Grade** | F (Not Acceptable) |
| **Risk Level** | 🔴 HIGH |
| **Root Cause** | Silent failures + No verification |

---

## 🔍 Findings

### Finding 1: Tests ใช้ `graphiti_client=None`

**Evidence**:
```python
# test_mcp_layer_tools.py:64-68
return SynapseService(
    graphiti_client=None,  # <-- NO GRAPHITI!
    layer_manager=layer_manager,
    user_id="test_user",
)

# test_identity_model.py:55
graphiti_client=None

# test_oracle_tools.py:66
graphiti_client=None
```

**Impact**: Tests ทั้งหมดไม่ได้ verify ว่า Graphiti writes ทำงาน

---

### Finding 2: SemanticManager มี Silent Failures

**Evidence** (`semantic.py:232-244`):
```python
# Persist to Graphiti/FalkorDB
if self._graphiti is not None:
    try:
        await self._graphiti.add_episode(...)
        logger.debug(f"Entity persisted to Graphiti")
    except Exception as e:
        logger.warning(f"Failed to persist entity to Graphiti: {e}")
        # <-- ไม่ re-raise! Data สูญหายโดยไม่รู้ตัว
```

**Impact**:
- Graphiti fail → Data ไม่ลง graph แต่ไม่มี error
- Return SynapseNode ที่เก็บแค่ใน memory/local

---

### Finding 3: _ensure_graphiti() Fail Silently

**Evidence** (`semantic.py:79-93`):
```python
async def _ensure_graphiti(self, require: bool = False) -> bool:
    if self._graphiti is None:
        try:
            from graphiti_core import Graphiti
            self._graphiti = Graphiti()  # Default constructor = NO DB!
        except Exception as exc:
            if require:
                raise RuntimeError(...)
            return False  # <-- Silent failure!
    return True
```

**Impact**:
- Default `Graphiti()` ไม่มี database connection
- `require=False` เป็น default → fail ไม่มี error

---

### Finding 4: Data Flow Analysis

```
User Input
    │
    ▼
SynapseService.add_memory()
    │
    ├──► LayerManager._route_to_layer()
    │         │
    │         ├──► Layer 1 (UserModel) → SQLite ✅
    │         ├──► Layer 2 (Procedural) → SQLite ✅
    │         ├──► Layer 3 (Semantic) → Qdrant + Graphiti ❌
    │         ├──► Layer 4 (Episodic) → SQLite + TTL ✅
    │         └──► Layer 5 (Working) → Memory ✅
    │
    └──► Graphiti.add_episode()
              │
              ▼
         [Try/Except]
              │
              ├──► Success → Graph DB populated
              └──► Fail → logger.warning() → Silent loss!
```

---

### Finding 5: Mock Ratio Analysis

| Test File | Mock Count | Real Graphiti |
|-----------|------------|---------------|
| test_phase1.py | 77 | ❌ Mock |
| test_mcp_layer_tools.py | 1 | ❌ None |
| test_identity_model.py | 1 | ❌ None |
| test_oracle_tools.py | 1 | ❌ None |
| test_qa_comprehensive.py | 20 | ❌ Mock |

**Total Mock References**: 152 occurrences

**Tests with Real Graphiti**: 0

---

## 📊 Layer Value Analysis

### ถ้า Graphiti ไม่ทำงาน:

| Layer | Storage | Value Without Graph | Status |
|-------|---------|---------------------|--------|
| L1: User Model | SQLite | ✅ Full value | Works |
| L2: Procedural | SQLite | ✅ Full value | Works |
| L3: Semantic | Qdrant + **Graph** | ⚠️ Vector only | **Degraded** |
| L4: Episodic | SQLite + TTL | ✅ Full value | Works |
| L5: Working | Memory | ✅ Full value | Works |

### สิ่งที่ขาดหายไปถ้าไม่มี Graph:

1. **Entity Relationships** - ไม่มี edges/facts
2. **Graph Traversal** - ไม่มี `get_related_entities()`
3. **Temporal Queries** - ไม่มี `valid_at`/`invalid_at`
4. **Knowledge Evolution** - ไม่มี supersede pattern
5. **LLM Extraction** - Entities ไม่ถูก extract อัตโนมัติ

---

## 🧪 Required Tests (Missing)

### Test 1: Graphiti Write Verification
```python
@pytest.mark.integration
async def test_graphiti_write_persists_to_database():
    """Verify that add_episode actually writes to graph database."""
    # Setup real Graphiti with test DB
    graphiti = await create_test_graphiti()

    # Add entity
    result = await graphiti.add_episode(
        name="test_entity",
        episode_body="Python is a programming language",
    )

    # VERIFY: Query the database directly
    nodes = await graphiti.search(query="Python", num_results=10)
    assert len(nodes) > 0, "No data in graph!"

    # VERIFY: Check entity exists
    assert any("Python" in str(n) for n in nodes)
```

### Test 2: End-to-End Flow
```python
@pytest.mark.integration
async def test_synapse_service_writes_to_graph():
    """Verify SynapseService.add_memory() populates graph."""
    service = SynapseService(graphiti_client=real_graphiti)

    result = await service.add_memory(
        name="test",
        episode_body="User prefers Python",
    )

    # VERIFY: Graphiti was called
    assert result["graphiti_result"] is not None

    # VERIFY: Data in graph
    search = await real_graphiti.search(query="Python")
    assert len(search) > 0
```

### Test 3: Silent Failure Detection
```python
def test_graphiti_failure_raises_error():
    """Verify that Graphiti failures are not silent."""
    broken_graphiti = BrokenGraphiti()  # Always fails

    service = SynapseService(graphiti_client=broken_graphiti)

    # SHOULD raise, not silently fail
    with pytest.raises(GraphitiWriteError):
        await service.add_memory(name="test", episode_body="data")
```

---

## 🎯 Recommendations

### Immediate (P0)

1. **Add Graphiti Integration Tests**
   - Create `tests/test_graphiti_integration.py`
   - Use Docker FalkorDB/Neo4j for CI
   - Verify actual database writes

2. **Fail Fast on Graphiti Errors**
   ```python
   # semantic.py - Change to:
   if self._graphiti is not None:
       try:
           await self._graphiti.add_episode(...)
       except Exception as e:
           logger.error(f"Graphiti write failed: {e}")
           raise GraphitiWriteError(f"Failed to persist: {e}") from e
   ```

3. **Add Health Check**
   ```python
   async def verify_graphiti_connection(self) -> bool:
       """Verify Graphiti is connected and writable."""
       try:
           await self._graphiti.search(query="__health_check__", num_results=1)
           return True
       except Exception:
           return False
   ```

### Short-term (P1)

4. **Make Graphiti Required in Production**
   - Add `SYNAPSE_REQUIRE_GRAPHITI=true` env var
   - Fail startup if Graphiti unavailable

5. **Add Metrics**
   - Track Graphiti write success/failure rate
   - Alert on degradation

6. **Update Tests**
   - Add `@pytest.mark.integration` for real DB tests
   - Keep mocks for unit tests only

---

## 📋 Checklist

- [ ] Create integration test file
- [ ] Add FalkorDB Docker compose for CI
- [ ] Change silent failures to raise errors
- [ ] Add health check endpoint
- [ ] Update documentation
- [ ] Add metrics/monitoring

---

## 🔗 Related Files

| File | Issue |
|------|-------|
| `synapse/layers/semantic.py` | Silent failures at L233-244, L292-304 |
| `synapse/services/synapse_service.py` | Try/except at L184-207 |
| `tests/test_*.py` | All use `graphiti_client=None` |

---

**Conclusion**: Synapse's core value proposition (Layer 3 Graph) is **not verified** by tests and has **silent failures**. Without fixing this, the system is just SQLite + Vector Store.

---

*Generated by Orga (QA Agent) — "Tests passing ≠ System correct"*
