# Synapse Frontend — Quality Gates Overview

> **Owner:** ออก้า (Orga) — Quality Assurance Specialist
> **Created:** 2026-03-17
> **Motto:** "Tests passing ≠ System correct"

---

## Quality Philosophy

```
Evidence over Assumptions
Integration over Mocks
Performance over Features
Security over Convenience
```

---

## Overall Quality Targets

| Metric | Target | Phase |
|--------|--------|-------|
| TypeScript Coverage | 100% (strict mode) | P1 |
| Unit Test Coverage | 85%+ | All |
| Integration Test Coverage | 80%+ | All |
| E2E Test Coverage | Critical paths | All |
| Lighthouse Performance | 95+ | P4 |
| Lighthouse Accessibility | 90+ | P4 |
| Bundle Size (gzip) | < 120KB | P4 |
| First Contentful Paint | < 800ms | P4 |
| Graph 1000 nodes | 60fps | P2 |

---

## Phase Quality Gates Summary

### Phase 1: Foundation

**Entry Criteria:**
- MCP Server running on :47780
- Bun v1.2+ installed
- Node.js 20+ available

**Exit Criteria (10 gates):**
| ID | Gate | Priority |
|----|------|----------|
| QG1.1 | App starts without errors | P0 |
| QG1.2 | All 5 sidebar icons render | P0 |
| QG1.3 | Command bar parses `search` | P0 |
| QG1.4 | Feed displays 10+ entries | P0 |
| QG1.5 | Layer filters toggle | P1 |
| QG1.6 | Identity badge visible | P1 |
| QG1.7 | MCP client connects | P0 |
| QG1.8 | TypeScript 0 errors | P0 |
| QG1.9 | Lighthouse > 90 | P1 |
| QG1.10 | No console errors | P0 |

**Tests Required:**
- Unit: 10+ tests, 80% lib/ coverage
- Integration: 3+ API route tests
- E2E: 2+ (feed render, command execute)

---

### Phase 2: Graph Explorer

**Entry Criteria:**
- Phase 1 all gates passed
- FalkorDB has 100+ nodes
- Canvas API supported

**Exit Criteria (10 gates):**
| ID | Gate | Priority |
|----|------|----------|
| QG2.1 | Canvas renders graph | P0 |
| QG2.2 | Pan/zoom at 60fps | P0 |
| QG2.3 | Node click → drawer | P0 |
| QG2.4 | Double-click expands | P1 |
| QG2.5 | Filters update < 100ms | P1 |
| QG2.6 | Depth slider works | P1 |
| QG2.7 | Layout toggle works | P2 |
| QG2.8 | Search highlights nodes | P1 |
| QG2.9 | 1000 nodes at 60fps | P0 |
| QG2.10 | No memory leaks (5 min) | P0 |

**Tests Required:**
- Unit: 15+ tests, 85% graph components
- Integration: 5+ data flow tests
- E2E: 3+ (pan, zoom, select, filter)
- Performance: 3 benchmarks (100/500/1000 nodes)

---

### Phase 3: CRUD Operations

**Entry Criteria:**
- Phase 2 all gates passed
- 5+ procedures exist
- User model accessible

**Exit Criteria (12 gates):**
| ID | Gate | Priority |
|----|------|----------|
| QG3.1 | Table displays procedures | P0 |
| QG3.2 | Sorting works | P1 |
| QG3.3 | Row expand shows steps | P0 |
| QG3.4 | Add creates entry | P0 |
| QG3.5 | Edit updates entry | P0 |
| QG3.6 | Delete removes (confirmed) | P0 |
| QG3.7 | Record success updates count | P0 |
| QG3.8 | Identity switcher works | P0 |
| QG3.9 | Preferences save | P0 |
| QG3.10 | Tag input works | P1 |
| QG3.11 | Form validation shows errors | P0 |
| QG3.12 | Optimistic updates work | P1 |

**Tests Required:**
- Unit: 20+ tests, 85% forms/tables
- Integration: 8+ CRUD operation tests
- E2E: 5+ (add, edit, delete, switch)

---

### Phase 4: Polish & Production

**Entry Criteria:**
- Phase 3 all gates passed
- All services healthy
- Oracle tools available

**Exit Criteria (16 gates):**
| ID | Gate | Priority |
|----|------|----------|
| QG4.1 | Dashboard shows statuses | P0 |
| QG4.2 | Stats update real-time | P1 |
| QG4.3 | Decay curve renders | P1 |
| QG4.4 | Oracle commands work | P1 |
| QG4.5 | Consolidation dry-run | P1 |
| QG4.6 | Consolidation execute | P1 |
| QG4.7 | Autocomplete shows matches | P1 |
| QG4.8 | Keyboard navigation | P1 |
| QG4.9 | Toast notifications | P0 |
| QG4.10 | Retry logic works | P0 |
| QG4.11 | Thai text renders | P1 |
| QG4.12 | Responsive layout | P1 |
| QG4.13 | Docker build succeeds | P0 |
| QG4.14 | Docker container connects | P0 |
| QG4.15 | Lighthouse > 95 | P0 |
| QG4.16 | Bundle < 120KB gzip | P0 |

**Tests Required:**
- Unit: 25+ tests, 85% overall
- Integration: 10+ all API routes
- E2E: 8+ full user flows
- Performance: 5+ (load, bundle, render)
- Accessibility: 10+ (ARIA, keyboard)

---

## Test Strategy

### Unit Tests
```
Framework: Bun test runner
Location: __tests__/unit/
Pattern: *.test.ts
Coverage: 85%+
```

### Integration Tests
```
Framework: Bun + MSW (Mock Service Worker)
Location: __tests__/integration/
Pattern: *.integration.test.ts
Coverage: 80%+
```

### E2E Tests
```
Framework: Playwright
Location: e2e/
Pattern: *.spec.ts
Browsers: Chrome, Firefox, Safari
```

### Performance Tests
```
Tools: Lighthouse, Chrome DevTools
Location: __tests__/performance/
Targets: See metrics above
```

---

## Quality Scoring

| Grade | Score | Meaning |
|-------|-------|---------|
| **A** | 90-100 | Production Ready |
| **B** | 80-89 | Good, minor gaps |
| **C** | 70-79 | Acceptable, needs work |
| **D** | 60-69 | Poor, significant gaps |
| **F** | < 60 | Not acceptable |

**Minimum for Production: Grade B (80+)**

---

## Gate Review Process

```
1. Developer completes phase
2. Run all automated tests
3. Orga reviews test results
4. Orga executes manual gates
5. Calculate quality score
6. If Grade < B: Return for fixes
7. If Grade >= B: Approve for next phase
```

---

## Regression Testing

After each phase completion:
- [ ] All previous phase gates still pass
- [ ] No new console errors
- [ ] No performance regressions
- [ ] Bundle size within limits

---

## Continuous Monitoring

| Metric | Tool | Frequency |
|--------|------|-----------|
| Bundle Size | Bundlephobia | Per build |
| Lighthouse | CI | Per PR |
| Coverage | Istanbul | Per build |
| Type Errors | tsc | Per build |

---

## Sign-off Template

```markdown
## Phase X Sign-off

**Date:** YYYY-MM-DD
**Reviewer:** ออก้า (Orga)
**Phase:** Phase X - [Name]

### Quality Gates Status
- Passed: X/10
- Failed: Y/10
- Blocked: Z/10

### Quality Score
- Grade: [A/B/C/D/F]
- Score: XX/100

### Issues Found
1. [Issue description]
2. [Issue description]

### Recommendation
- [ ] APPROVED - Proceed to Phase X+1
- [ ] CONDITIONAL - Fix issues, then proceed
- [ ] BLOCKED - Major issues require rework

### Notes
[Additional notes]

---
**Signed:** ออก้า (Orga)
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-03-17 | Created by Orga |
