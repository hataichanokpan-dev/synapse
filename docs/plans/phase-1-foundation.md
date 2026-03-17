# Phase 1 — Foundation (Shell + Feed)

> **Owner:** นีโอ (Neo) — Project Manager
> **QA Owner:** ออก้า (Orga) — Quality Assurance
> **Status:** 📋 Planned
> **Created:** 2026-03-17

---

## Goal

> Open the app and see a live memory feed in a terminal-like interface.

---

## Scope

### In Scope
- Next.js 16+ scaffold with Bun + Turbopack
- Design system setup (Tailwind v4 config)
- Shell layout (Sidebar + Top bar + Command bar + Content area)
- MCP client library (typed HTTP client)
- Feed view (SSE/polling stream → virtualized list)
- Command bar basic (search, status commands)
- Identity display (top bar)

### Out of Scope
- Graph visualization (Phase 2)
- Procedures CRUD (Phase 3)
- System dashboard (Phase 4)
- Thai text rendering optimization (Phase 4)

---

## Tasks

### 1.1 Project Scaffold
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Create Next.js 16+ project with Bun | 15m | ⬜ | `bun create next-app synapse-ui --ts --tailwind --app --turbopack` |
| Setup Tailwind v4 config | 20m | ⬜ | Colors, fonts, spacing from design system |
| Add JetBrains Mono font | 10m | ⬜ | woff2 files in public/fonts |
| Setup TypeScript strict mode | 5m | ⬜ | tsconfig.json |
| Create base directory structure | 10m | ⬜ | components/, lib/, app/api/ |

### 1.2 Shell Layout
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Sidebar component (56px collapsed) | 30m | ⬜ | Icons only, expand on hover |
| Top bar component (40px) | 20m | ⬜ | Title + identity badge + settings |
| Command bar component (36px) | 30m | ⬜ | Bottom input + autocomplete |
| Shell layout wrapper | 20m | ⬜ | Grid layout with areas |

### 1.3 MCP Client Library
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Type definitions (memory, graph, identity, system) | 45m | ⬜ | lib/types/*.ts |
| HTTP client wrapper | 30m | ⬜ | lib/mcp-client.ts |
| API routes scaffold | 30m | ⬜ | app/api/memory/*, /graph/*, etc. |
| Error handling + retry logic | 20m | ⬜ | Toast notifications |

### 1.4 Feed View
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Feed list component (virtualized) | 45m | ⬜ | TanStack Virtual |
| Feed entry component | 30m | ⬜ | Single event row styling |
| Layer filter chips | 20m | ⬜ | ALL, SEMANTIC, EPISODIC, etc. |
| SSE/polling hook | 30m | ⬜ | lib/hooks/use-feed.ts |
| Live mode indicator | 10m | ⬜ | Green dot = connected |

### 1.5 Command Bar (Basic)
| Task | Est. | Status | Notes |
|------|------|--------|-------|
| Command parser | 30m | ⬜ | lib/command-parser.ts |
| search command | 15m | ⬜ | `search <query> [--layer] [--limit]` |
| status command | 10m | ⬜ | `status` |
| Autocomplete stub | 20m | ⬜ | Fuzzy match commands |
| History (localStorage) | 15m | ⬜ | Up/Down arrows |

---

## Dependencies

```
External:
  - Synapse MCP Server running on :47780
  - FalkorDB running
  - At least some memory data exists

Internal:
  - None (first phase)
```

---

## Quality Gates (by Orga)

### Entry Criteria
- [ ] Synapse MCP server confirmed running
- [ ] Bun installed (v1.2+)
- [ ] Node.js 20+ available as fallback

### Exit Criteria
- [ ] **QG1.1:** App starts without errors (`bun dev`)
- [ ] **QG1.2:** All 5 sidebar icons render correctly
- [ ] **QG1.3:** Command bar accepts input and parses `search` command
- [ ] **QG1.4:** Feed displays at least 10 mock/real entries
- [ ] **QG1.5:** Layer filter chips toggle correctly
- [ ] **QG1.6:** Identity badge shows in top bar
- [ ] **QG1.7:** MCP client connects to server successfully
- [ ] **QG1.8:** TypeScript compiles with 0 errors
- [ ] **QG1.9:** Lighthouse Performance > 90
- [ ] **QG1.10:** No console errors in browser

### Test Requirements
| Test Type | Count | Coverage Target |
|-----------|-------|-----------------|
| Unit Tests | 10+ | 80% of lib/ |
| Integration Tests | 3+ | API routes |
| E2E Tests | 2+ | Feed render, command execute |

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Next.js 16 breaking changes | Medium | High | Pin to specific version, check release notes |
| Tailwind v4 config differs from v3 | High | Medium | Use official migration guide |
| SSE connection issues | Medium | Medium | Fallback to polling, show connection status |
| Virtualized list performance | Low | Medium | Test with 1000+ items early |

---

## Deliverables

1. Working Next.js 16+ app at `localhost:3000`
2. Shell layout with sidebar, top bar, command bar
3. Feed view showing live memory events
4. Basic command bar with search + status
5. MCP client library (typed)
6. Phase 1 QA report from Orga

---

## Next Phase

→ **Phase 2:** Graph Explorer (D3 Canvas, 60fps)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-17 | Created by Neo |
