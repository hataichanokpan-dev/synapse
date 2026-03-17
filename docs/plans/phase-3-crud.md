# Phase 3 — Procedures + Identity CRUD

> **Owner:** นีโอ (Neo) — Project Manager
> **QA Owner:** ออก้า (Orga) — Quality Assurance
> **Status:** 📋 Planned
> **Created:** 2026-03-17
> **Depends on:** Phase 2

---

## Goal

> Full CRUD for Layer 2 procedures and Layer 1 user preferences without terminal commands.

---

## Scope

### In Scope
- Procedure table (sortable, expandable)
- Add/edit/delete procedure forms
- Record success action
- Identity switcher (user context)
- Preferences editor (language, timezone, expertise, topics, notes)
- Tag input component with autocomplete

### Out of Scope
- Procedure versioning (future)
- User management (multi-user auth)
- Import/export preferences (Phase 4)

---

## Tasks

### 3.1 Procedure Table
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Table component | 30m | ⬜ | Virtualized for large lists |
| Sortable columns | 20m | ⬜ | trigger, success, decay, topics |
| Expandable row | 25m | ⬜ | Show steps on click |
| Row actions | 20m | ⬜ | Record Success, Edit, Delete |
| Empty state | 10m | ⬜ | "No procedures yet" |

### 3.2 Procedure Forms
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Add procedure modal | 30m | ⬜ | Trigger, steps, topics |
| Edit procedure modal | 25m | ⬜ | Pre-fill existing data |
| Delete confirmation | 15m | ⬜ | "Are you sure?" dialog |
| Form validation | 20m | ⬜ | Required fields, length limits |
| API integration | 20m | ⬜ | POST /api/procedures |

### 3.3 Record Success
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| One-click button | 15m | ⬜ | In row action |
| Optimistic update | 15m | ⬜ | Update UI immediately |
| API call | 10m | ⬜ | POST /api/procedures/success |
| Toast notification | 10m | ⬜ | "Success recorded" |

### 3.4 Identity Switcher
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| User dropdown | 20m | ⬜ | List available users |
| Agent dropdown | 15m | ⬜ | List available agents |
| Chat context | 15m | ⬜ | Current chat ID |
| Clear buttons | 10m | ⬜ | Clear agent/chat |
| API integration | 15m | ⬜ | PUT /api/identity |

### 3.5 Preferences Editor
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Language dropdown | 15m | ⬜ | th, en |
| Timezone selector | 15m | ⬜ | Common timezones |
| Response style dropdown | 10m | ⬜ | concise, detailed |
| Expertise tag input | 25m | ⬜ | Add/remove tags |
| Topics tag input | 20m | ⬜ | Add/remove tags |
| Notes textarea | 10m | ⬜ | Free-form text |
| Save button + validation | 15m | ⬜ | PUT /api/user/preferences |

### 3.6 Tag Input Component
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Tag chip with remove | 15m | ⬜ | × button |
| Add input with autocomplete | 25m | ⬜ | Fuzzy match existing tags |
| Keyboard navigation | 15m | ⬜ | Enter, Tab, Backspace |
| Max tags limit | 10m | ⬜ | Show warning at limit |

---

## Dependencies

```
External:
  - Synapse Layer 2 (procedural) populated
  - Synapse Layer 1 (user_model) accessible

Internal:
  - Phase 1 MCP client library
  - Phase 1 modal component
  - Phase 1 form components
```

---

## Quality Gates (by Orga)

### Entry Criteria
- [ ] Phase 2 complete and passing all quality gates
- [ ] At least 5 procedures exist for testing
- [ ] User model accessible via MCP

### Exit Criteria
- [ ] **QG3.1:** Procedure table displays all procedures
- [ ] **QG3.2:** Sorting works on all columns
- [ ] **QG3.3:** Row expand shows procedure steps
- [ ] **QG3.4:** Add procedure creates new entry
- [ ] **QG3.5:** Edit procedure updates existing entry
- [ ] **QG3.6:** Delete procedure removes entry (with confirmation)
- [ ] **QG3.7:** Record success increments count + updates decay
- [ ] **QG3.8:** Identity switcher changes user context
- [ ] **QG3.9:** Preferences form saves all fields
- [ ] **QG3.10:** Tag input adds/removes tags correctly
- [ ] **QG3.11:** Form validation shows errors
- [ ] **QG3.12:** Optimistic updates work (no loading delay)

### Test Requirements
| Test Type | Count | Coverage Target |
|-----------|-------|-----------------|
| Unit Tests | 20+ | 85% of forms, tables |
| Integration Tests | 8+ | CRUD operations |
| E2E Tests | 5+ | Add, edit, delete, switch identity |

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Form state complexity | Medium | Medium | Use Zustand for form state |
| Tag autocomplete performance | Low | Low | Debounce input, limit results |
| Concurrent edits | Low | Medium | Optimistic locking, last-write-wins |

---

## Deliverables

1. Procedures view at `/procedures` route
2. Identity view at `/identity` route
3. Procedure table with CRUD
4. Preferences editor with tag inputs
5. Identity switcher component
6. Phase 3 QA report from Orga

---

## Next Phase

→ **Phase 4:** System Dashboard + Oracle + Polish

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-17 | Created by Neo |
