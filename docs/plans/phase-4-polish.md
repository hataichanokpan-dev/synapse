# Phase 4 — System Dashboard + Oracle + Polish

> **Owner:** นีโอ (Neo) — Project Manager
> **QA Owner:** ออก้า (Orga) — Quality Assurance
> **Status:** 📋 Planned
> **Created:** 2026-03-17
> **Depends on:** Phase 3

---

## Goal

> Production-ready management dashboard with oracle tools, system health, and polish.

---

## Scope

### In Scope
- Service health grid
- Memory statistics (live counts)
- Decay curve chart (D3)
- Oracle commands (consult, reflect, analyze)
- Consolidation UI (dry-run → confirm → execute)
- Complete command bar (all commands, autocomplete, history)
- Error handling (toast, retry, offline)
- Thai text rendering optimization
- Responsive breakpoints
- Docker integration

### Out of Scope
- User authentication (future)
- Multi-tenant support (future)
- Mobile app (future)

---

## Tasks

### 4.1 System Dashboard
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Service health grid | 25m | ⬜ | MCP, FalkorDB, Qdrant, Graphiti |
| Memory stats display | 20m | ⬜ | Entities, edges, episodes, procedures |
| Decay curve chart | 45m | ⬜ | D3 line chart with formulas |
| Config display | 15m | ⬜ | Read-only LLM, embedder, semaphore |
| Maintenance actions | 20m | ⬜ | Run Decay, Clear Graph (dangerous) |

### 4.2 Oracle Tools
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Command: consult | 20m | ⬜ | POST /api/oracle/consult |
| Command: reflect | 15m | ⬜ | POST /api/oracle/reflect |
| Command: analyze | 25m | ⬜ | POST /api/oracle/analyze |
| Oracle UI panel | 30m | ⬜ | Optional dedicated view |
| Result display | 20m | ⬜ | Formatted oracle output |

### 4.3 Consolidation UI
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Dry-run preview | 25m | ⬜ | Show what will be consolidated |
| Confirmation dialog | 15m | ⬜ | Review before execute |
| Execute + progress | 20m | ⬜ | Show consolidation progress |
| Result summary | 15m | ⬜ | Items consolidated, space saved |

### 4.4 Command Bar Complete
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| All commands implemented | 30m | ⬜ | 12+ commands from plan |
| Fuzzy autocomplete | 25m | ⬜ | Match commands + entities |
| Keyboard navigation | 15m | ⬜ | ↑/↓/Tab/Enter/Esc |
| History persistence | 15m | ⬜ | localStorage, max 50 items |
| Output formatting | 20m | ⬜ | Highlighted results in feed |

### 4.5 Error Handling
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Toast notification system | 25m | ⬜ | Success, error, warning |
| Retry logic | 20m | ⬜ | Exponential backoff |
| Offline detection | 15m | ⬜ | Show connection lost banner |
| Error boundary | 15m | ⬜ | Catch React errors gracefully |

### 4.6 Polish & Accessibility
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Thai text rendering | 20m | ⬜ | Font fallback, line-height |
| Responsive breakpoints | 30m | ⬜ | Mobile, tablet, desktop |
| Keyboard accessibility | 25m | ⬜ | Tab navigation, focus states |
| ARIA labels | 20m | ⬜ | Screen reader support |
| Loading states | 15m | ⬜ | Skeletons, spinners |

### 4.7 Docker Integration
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Dockerfile | 20m | ⬜ | Multi-stage build |
| docker-compose.yml | 15m | ⬜ | Extend parent compose |
| Environment config | 10m | ⬜ | MCP_SERVER_URL |
| Health check | 10m | ⬜ | /api/health endpoint |

---

## Dependencies

```
External:
  - All Synapse services running
  - Docker installed for deployment

Internal:
  - Phase 1-3 complete
  - All API routes working
```

---

## Quality Gates (by Orga)

### Entry Criteria
- [ ] Phase 3 complete and passing all quality gates
- [ ] All Synapse services healthy
- [ ] Oracle tools available in MCP server

### Exit Criteria
- [ ] **QG4.1:** System dashboard shows all service statuses
- [ ] **QG4.2:** Memory stats update in real-time
- [ ] **QG4.3:** Decay curve renders correctly
- [ ] **QG4.4:** Oracle commands return valid results
- [ ] **QG4.5:** Consolidation dry-run shows preview
- [ ] **QG4.6:** Consolidation execute works with confirmation
- [ ] **QG4.7:** Command bar autocomplete shows matches
- [ ] **QG4.8:** Keyboard navigation works in command bar
- [ ] **QG4.9:** Toast notifications appear for errors
- [ ] **QG4.10:** Retry logic works (test with network failure)
- [ ] **QG4.11:** Thai text renders correctly (no overlap)
- [ ] **QG4.12:** Responsive layout works on mobile
- [ ] **QG4.13:** Docker build succeeds
- [ ] **QG4.14:** Docker container starts and connects
- [ ] **QG4.15:** Lighthouse score > 95 (Performance)
- [ ] **QG4.16:** Bundle size < 120KB gzipped

### Test Requirements
| Test Type | Count | Coverage Target |
|-----------|-------|-----------------|
| Unit Tests | 25+ | 85% overall |
| Integration Tests | 10+ | All API routes |
| E2E Tests | 8+ | Full user flows |
| Performance Tests | 5+ | Load, bundle, render |
| Accessibility Tests | 10+ | ARIA, keyboard |

---

## Production Readiness Checklist

### Security
- [ ] No hardcoded secrets
- [ ] Environment variables validated
- [ ] XSS prevention (React default + sanitization)
- [ ] CORS configured correctly
- [ ] Rate limiting on API routes

### Performance
- [ ] First Contentful Paint < 800ms
- [ ] Feed entry render < 16ms
- [ ] Graph 1000 nodes at 60fps
- [ ] Command autocomplete < 50ms
- [ ] Bundle size < 120KB gzipped

### Reliability
- [ ] Error boundaries catch all errors
- [ ] Offline detection works
- [ ] Auto-reconnect on SSE
- [ ] Graceful degradation

### Operations
- [ ] Health check endpoint
- [ ] Docker image < 200MB
- [ ] Startup time < 5s
- [ ] Log output structured

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Bundle size exceeds target | Medium | Medium | Code splitting, tree shaking |
| Thai font rendering issues | Low | Low | Test early, adjust line-height |
| Docker networking issues | Medium | Medium | Use bridge network, test locally |
| Accessibility gaps | Medium | Low | Automated + manual testing |

---

## Deliverables

1. System view at `/system` route
2. Oracle tools integrated
3. Consolidation UI
4. Complete command bar
5. Error handling system
6. Responsive design
7. Docker deployment ready
8. Phase 4 QA report from Orga
9. Production readiness certification

---

## Final Deliverable

**Synapse UI v1.0** — Production-ready frontend

- All 5 views working
- All commands working
- Docker deployment
- QA certified by Orga

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-17 | Created by Neo |
