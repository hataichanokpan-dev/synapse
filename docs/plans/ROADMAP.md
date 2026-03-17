# Synapse Frontend — Implementation Roadmap

> **Created by:** นีโอ (Neo) 🧭
> **QA by:** ออก้า (Orga) 🛡️
> **Date:** 2026-03-17

---

## Overview

| Item | Value |
|------|-------|
| **Stack** | Next.js 16+ / Bun / Tailwind v4 / D3 / Zustand |
| **Design** | Terminal Glass (Dark + Monospace) |
| **Views** | 5 (Feed, Graph, Procedures, Identity, System) |
| **Phases** | 4 |
| **Quality Target** | Grade B+ (80+) |

---

## Phase Timeline

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Foundation                                        │
│  ─────────────────────                                      │
│  Shell + Feed + MCP Client + Command Bar                    │
│  Gates: 10 | Tests: 15+ | Est: 2-3 days                     │
├─────────────────────────────────────────────────────────────┤
│                          ↓                                  │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: Graph Explorer                                    │
│  ───────────────────────                                    │
│  D3 Canvas + Interactions + Filters                         │
│  Gates: 10 | Tests: 23+ | Est: 2-3 days                     │
├─────────────────────────────────────────────────────────────┤
│                          ↓                                  │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: CRUD Operations                                   │
│  ────────────────────────                                   │
│  Procedures + Identity + Preferences                        │
│  Gates: 12 | Tests: 33+ | Est: 2-3 days                     │
├─────────────────────────────────────────────────────────────┤
│                          ↓                                  │
├─────────────────────────────────────────────────────────────┤
│  Phase 4: Polish & Production                               │
│  ─────────────────────────────                              │
│  System Dashboard + Oracle + Docker + Polish                │
│  Gates: 16 | Tests: 58+ | Est: 2-3 days                     │
└─────────────────────────────────────────────────────────────┘

Total Gates: 48
Total Tests: 129+
Estimated: 8-12 days
```

---

## Files Created

| File | Description |
|------|-------------|
| `frontend_plan.md` | Full technical plan (updated to Next.js 16+) |
| `phase-1-foundation.md` | Phase 1 detailed tasks + gates |
| `phase-2-graph.md` | Phase 2 detailed tasks + gates |
| `phase-3-crud.md` | Phase 3 detailed tasks + gates |
| `phase-4-polish.md` | Phase 4 detailed tasks + gates |
| `quality-gates-overview.md` | All quality gates + test strategy |
| `ROADMAP.md` | This file |

---

## Quick Reference

### Start Phase 1
```bash
cd /c/Programing/PersonalAI/synapse
bun create next-app synapse-ui --ts --tailwind --app --turbopack
cd synapse-ui
bun dev
```

### Check Quality Gates
```bash
# Run all tests
bun test

# Check TypeScript
bunx tsc --noEmit

# Check bundle size
bun run build && du -sh .next/

# Lighthouse
bunx lighthouse http://localhost:3000 --output=json
```

### Before Each Phase
1. Review phase plan file
2. Check entry criteria
3. Ensure dependencies met

### After Each Phase
1. Run all automated tests
2. Execute manual quality gates
3. Calculate quality score
4. Get Orga sign-off

---

## Quality Targets Summary

| Phase | Unit Tests | Integration | E2E | Min Grade |
|-------|------------|-------------|-----|-----------|
| P1 | 10+ (80%) | 3+ | 2+ | B (80+) |
| P2 | 15+ (85%) | 5+ | 3+ | B (80+) |
| P3 | 20+ (85%) | 8+ | 5+ | B (80+) |
| P4 | 25+ (85%) | 10+ | 8+ | B+ (85+) |

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | Next.js 16+ | Turbopack stable, RSC, App Router |
| Runtime | Bun | 4× faster, native TypeScript |
| Styling | Tailwind v4 | Utility-first, terminal aesthetic |
| Graph | Canvas (not SVG) | 60fps on 1000+ nodes |
| State | Zustand | 1KB, simple, sufficient |
| Testing | Bun + Playwright | Fast, integrated |

---

## Risk Register

| Risk | Phase | Mitigation |
|------|-------|------------|
| Next.js 16 breaking changes | P1 | Pin version, check release notes |
| Canvas performance < 60fps | P2 | WebGL fallback, node clustering |
| Form state complexity | P3 | Zustand for form state |
| Bundle size exceeds 120KB | P4 | Code splitting, tree shaking |

---

## Next Steps

1. ✅ Review `frontend_plan.md` for technical details
2. ✅ Review phase plans for task breakdown
3. ✅ Review `quality-gates-overview.md` for QA requirements
4. ⬜ **Start Phase 1** — Foundation

---

## Team

| Role | Agent | Responsibility |
|------|-------|----------------|
| Coordinator | ฝน (Fon) | Overall coordination |
| PM/Planner | นีโอ (Neo) | Plans, roadmaps, milestones |
| Developer | โจ (Joe) | Implementation |
| QA | ออก้า (Orga) | Quality gates, testing |

---

*Last updated: 2026-03-17*
