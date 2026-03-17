# Phase 2 — Graph Explorer

> **Owner:** นีโอ (Neo) — Project Manager
> **QA Owner:** ออก้า (Orga) — Quality Assurance
> **Status:** 📋 Planned
> **Created:** 2026-03-17
> **Depends on:** Phase 1

---

## Goal

> Interactive knowledge graph visualization with 60fps performance on 1000+ nodes.

---

## Scope

### In Scope
- D3 force-directed graph on HTML5 Canvas
- Node/edge fetch via API routes
- Interaction layer (click, drag, zoom, expand)
- Detail drawer (bottom sheet)
- Entity type filters
- Depth control slider
- Layout options (force, tree, radial)

### Out of Scope
- Edge editing (Phase 3+)
- Node creation via UI (Phase 3+)
- Export functionality (Phase 4)

---

## Tasks

### 2.1 Canvas Renderer
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Setup D3 force simulation | 30m | ⬜ | d3-force, d3-scale |
| Canvas rendering loop | 45m | ⬜ | 60fps target, requestAnimationFrame |
| Node rendering (size, opacity, color) | 30m | ⬜ | Logarithmic size scale |
| Edge rendering (thickness, dashed) | 20m | ⬜ | Confidence-based thickness |
| Label rendering (truncation) | 15m | ⬜ | Max 20 chars |

### 2.2 Graph Data Fetching
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| API route: /api/graph/nodes | 20m | ⬜ | GET → search_nodes |
| API route: /api/graph/edges | 20m | ⬜ | GET → get_entity_edge |
| API route: /api/graph/episodes | 15m | ⬜ | GET → get_episodes |
| use-graph hook | 30m | ⬜ | Zustand store + TanStack Query |

### 2.3 Interaction Layer
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Pan (drag canvas) | 20m | ⬜ | Transform matrix |
| Zoom (scroll) | 15m | ⬜ | Scale transform |
| Click node → select | 15m | ⬜ | Highlight + drawer |
| Double-click → expand neighbors | 25m | ⬜ | Depth+1 fetch |
| Right-click → context menu | 20m | ⬜ | Delete edge/entity |
| Shift+click → multi-select | 20m | ⬜ | Batch operations |
| Hover → highlight edges | 15m | ⬜ | Ghost effect |

### 2.4 Detail Drawer
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Bottom sheet component | 30m | ⬜ | Framer Motion slide-up |
| Entity details display | 20m | ⬜ | Name, type, decay, created |
| Connected edges list | 20m | ⬜ | Clickable links |
| Episodes list | 15m | ⬜ | Source references |
| Action buttons | 15m | ⬜ | Delete, expand |

### 2.5 Filter Panel
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Entity type checkboxes | 20m | ⬜ | person, tech, concept, project, topic |
| Depth slider | 15m | ⬜ | 1-5 depth control |
| Layout toggle (force/tree/radial) | 30m | ⬜ | D3 layout switch |
| Search input | 15m | ⬜ | Fuzzy entity search |
| Filter state management | 15m | ⬜ | Zustand |

---

## Dependencies

```
External:
  - FalkorDB with existing graph data
  - Graphiti entity extraction working

Internal:
  - Phase 1 MCP client library
  - Phase 1 API route structure
  - Phase 1 shell layout
```

---

## Quality Gates (by Orga)

### Entry Criteria
- [ ] Phase 1 complete and passing all quality gates
- [ ] FalkorDB has at least 100 nodes for testing
- [ ] Canvas API supported in target browsers

### Performance Targets
| Metric | Target | Measurement |
|--------|--------|-------------|
| 100 nodes render | 60fps | Chrome DevTools |
| 500 nodes render | 60fps | Chrome DevTools |
| 1000 nodes render | 60fps | Chrome DevTools |
| Node click response | < 50ms | Performance.now() |
| Zoom animation | 60fps | requestAnimationFrame timing |

### Exit Criteria
- [ ] **QG2.1:** Canvas renders graph from FalkorDB data
- [ ] **QG2.2:** Pan + zoom work smoothly at 60fps
- [ ] **QG2.3:** Node click opens detail drawer
- [ ] **QG2.4:** Double-click expands neighbors (depth+1)
- [ ] **QG2.5:** Entity type filters update graph in < 100ms
- [ ] **QG2.6:** Depth slider changes traversal depth
- [ ] **QG2.7:** Layout toggle switches force/tree/radial
- [ ] **QG2.8:** Search highlights matching nodes
- [ ] **QG2.9:** 1000 nodes render at 60fps
- [ ] **QG2.10:** No memory leaks after 5 min interaction

### Test Requirements
| Test Type | Count | Coverage Target |
|-----------|-------|-----------------|
| Unit Tests | 15+ | 85% of graph components |
| Integration Tests | 5+ | API routes + data flow |
| E2E Tests | 3+ | Pan, zoom, select, filter |
| Performance Tests | 3+ | 100/500/1000 node benchmarks |

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Canvas performance < 60fps | Medium | High | WebGL fallback, node clustering |
| Large graph memory usage | Medium | Medium | Virtual rendering, lazy loading |
| D3 force simulation instability | Low | Medium | Tweak alpha, charge, link distance |
| Touch device support | Low | Low | Defer to Phase 4 |

---

## Deliverables

1. Graph view at `/graph` route
2. D3 Canvas renderer (60fps on 1000 nodes)
3. Interactive pan/zoom/select
4. Detail drawer with entity info
5. Filter panel (type, depth, layout, search)
6. Phase 2 QA report from Orga

---

## Next Phase

→ **Phase 3:** Procedures + Identity CRUD

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-17 | Created by Neo |
