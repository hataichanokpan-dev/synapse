# P0 Implementation Checklist — synapse

> **Created**: 2026-03-17T09:35+07:00
> **By**: Orga (QA Agent)
> **Target**: Production Ready

---

## 📋 Pre-Implementation

### Environment Setup
- [ ] Python environment active
- [ ] All dependencies installed
- [ ] Tests passing (`pytest tests/ -v`)
- [ ] No linting errors (`ruff check .`)

### Baseline
- [ ] Record current test count: **210**
- [ ] Record current coverage: **~65%**
- [ ] Record current grade: **C (72/100)**

---

## 🎯 Gap 1: MCP Layer Coverage (8-12h)

### Layer 1: User Model Tools

**Files**:
- `synapse/mcp_server/src/graphiti_mcp_server.py`
- `synapse/services/synapse_service.py`

#### Implementation
- [ ] Create `get_user_preferences()` MCP tool
- [ ] Create `update_user_preferences()` MCP tool
- [ ] Add `get_user_preferences()` to SynapseService
- [ ] Add `update_user_preferences()` to SynapseService

#### Tests
- [ ] Test `get_user_preferences` returns user model
- [ ] Test `update_user_preferences` updates fields
- [ ] Test `update_user_preferences` adds topics
- [ ] Test error handling (user not found)

#### Acceptance Criteria
- [ ] `mcp.run_tool("get_user_preferences")` returns valid user
- [ ] `mcp.run_tool("update_user_preferences", language="en")` works
- [ ] All 4 tests passing

---

### Layer 2: Procedural Tools

#### Implementation
- [ ] Create `find_procedures()` MCP tool
- [ ] Create `add_procedure()` MCP tool
- [ ] Create `record_procedure_success()` MCP tool
- [ ] Ensure SynapseService exposes these methods

#### Tests
- [ ] Test `find_procedures` matches trigger
- [ ] Test `add_procedure` creates procedure
- [ ] Test `record_procedure_success` increments count
- [ ] Test error handling (invalid procedure_id)

#### Acceptance Criteria
- [ ] Can add and retrieve procedures via MCP
- [ ] Success tracking works correctly
- [ ] All 4 tests passing

---

### Layer 5: Working Memory Tools

#### Implementation
- [ ] Create `get_working_context()` MCP tool
- [ ] Create `set_working_context()` MCP tool
- [ ] Create `clear_working_context()` MCP tool
- [ ] Add session_id support to WorkingManager

#### Tests
- [ ] Test `get_working_context` returns value
- [ ] Test `set_working_context` stores value
- [ ] Test `clear_working_context` removes all
- [ ] Test session isolation

#### Acceptance Criteria
- [ ] Working memory accessible via MCP
- [ ] Session isolation works
- [ ] All 4 tests passing

---

## 🎯 Gap 2: Identity Model (4-6h)

### Files
- `synapse/layers/types.py`
- `synapse/services/synapse_service.py`

#### Implementation
- [ ] Add `agent_id: Optional[str]` to `UserModel`
- [ ] Add `chat_id: Optional[str]` to `UserModel`
- [ ] Add `agent_id: Optional[str]` to `SynapseEpisode`
- [ ] Add `chat_id: Optional[str]` to `SynapseEpisode`
- [ ] Update `SynapseService.__init__` to accept agent_id, chat_id
- [ ] Add `set_context()` method to SynapseService

#### Tests
- [ ] Test UserModel accepts agent_id
- [ ] Test UserModel accepts chat_id
- [ ] Test SynapseEpisode has agent_id
- [ ] Test SynapseEpisode has chat_id
- [ ] Test SynapseService.set_context updates
- [ ] Test episodes store agent_id correctly

#### Acceptance Criteria
- [ ] Identity hierarchy: user → agent → chat → session
- [ ] Backward compatible (existing code works)
- [ ] All 6 tests passing

---

## 🎯 Gap 3: Oracle Tools (10-15h)

### Files
- `synapse/mcp_server/src/graphiti_mcp_server.py`
- `synapse/services/synapse_service.py`

### 3.1 synapse_consult (3-4h)

#### Implementation
- [ ] Design consult response structure
- [ ] Implement `consult()` in SynapseService
- [ ] Create `synapse_consult()` MCP tool
- [ ] Add multi-layer search integration

#### Tests
- [ ] Test returns structured guidance
- [ ] Test includes user preferences
- [ ] Test finds relevant procedures
- [ ] Test handles empty results

#### Acceptance Criteria
- [ ] Returns relevant patterns, episodes, preferences, procedures
- [ ] Includes synthesized recommendation
- [ ] All 4 tests passing

---

### 3.2 synapse_reflect (2-3h)

#### Implementation
- [ ] Implement `reflect()` in SynapseService
- [ ] Create `synapse_reflect()` MCP tool
- [ ] Add layer filtering support

#### Tests
- [ ] Test returns random insight
- [ ] Test filters by layer
- [ ] Test filters by topic
- [ ] Test handles empty memory

#### Acceptance Criteria
- [ ] Returns insight from specified or random layer
- [ ] Includes context and related items
- [ ] All 4 tests passing

---

### 3.3 synapse_analyze (3-4h)

#### Implementation
- [ ] Implement `analyze()` in SynapseService
- [ ] Create `synapse_analyze()` MCP tool
- [ ] Add pattern detection logic
- [ ] Add trend analysis
- [ ] Add gap identification

#### Tests
- [ ] Test identifies patterns
- [ ] Test finds knowledge gaps
- [ ] Test calculates memory health
- [ ] Test respects time range

#### Acceptance Criteria
- [ ] Returns analysis results for specified type
- [ ] Pattern detection works
- [ ] All 4 tests passing

---

### 3.4 synapse_consolidate (2-4h)

#### Implementation
- [ ] Implement `consolidate()` in SynapseService
- [ ] Create `synapse_consolidate()` MCP tool
- [ ] Add episode selection logic
- [ ] Add semantic promotion logic

#### Tests
- [ ] Test promotes qualified episodes
- [ ] Test respects min_access_count
- [ ] Test dry_run works
- [ ] Test skips unqualified episodes

#### Acceptance Criteria
- [ ] Episodes promoted to semantic memory
- [ ] Access count threshold respected
- [ ] All 4 tests passing

---

## 📊 Verification Checklist

### After Each Gap
- [ ] All new tests passing
- [ ] No regressions in existing tests
- [ ] Coverage increased
- [ ] Linting clean

### After All P0 Gaps
- [ ] Total tests ≥ 250 (from 210)
- [ ] Coverage ≥ 75% (from ~65%)
- [ ] Mock ratio < 35% (from 40%)
- [ ] Grade ≥ B (from C)

### Before Production
- [ ] All 15 P0 tests passing
- [ ] Integration tests passing
- [ ] Performance baseline recorded
- [ ] Documentation updated

---

## 🚀 Implementation Order (Recommended)

```
Day 1: Gap 2 (Identity Model)
├── Update types.py (1-2h)
├── Update SynapseService (1-2h)
├── Add tests (1-2h)
└── Verify: 6 new tests passing

Day 2: Gap 1.1 + 1.2 (User Model + Procedural)
├── Layer 1 MCP tools (3-4h)
├── Layer 2 MCP tools (2-3h)
├── Add tests (2h)
└── Verify: 8 new tests passing

Day 3: Gap 1.3 (Working Memory)
├── Layer 5 MCP tools (3-5h)
├── Add session support (1-2h)
├── Add tests (2h)
└── Verify: 4 new tests passing

Day 4: Gap 3.1 + 3.2 (consult + reflect)
├── synapse_consult (3-4h)
├── synapse_reflect (2-3h)
├── Add tests (2h)
└── Verify: 8 new tests passing

Day 5: Gap 3.3 + 3.4 (analyze + consolidate)
├── synapse_analyze (3-4h)
├── synapse_consolidate (2-4h)
├── Add tests (2h)
└── Verify: 8 new tests passing

Total: 22-33h, 34 new tests expected
```

---

## 📁 Deliverables

| Deliverable | Location |
|-------------|----------|
| QA Report | `.qa/reports/qa_report_2026-03-17.md` |
| This Checklist | `.qa/checklists/p0_implementation.md` |
| P0 Tests | `tests/test_p0_*.py` (to be created) |

---

*Orga — Because "tests passing" is not enough.*
