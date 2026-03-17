# Synapse Frontend — Full Plan

> **Design philosophy:** _"Less but more"_ — every pixel earns its place.
> **Aesthetic:** iOS-terminal hybrid. Monospace. Dark. Breathing space. Data-dense yet calm.

---

## 1. Tech Stack Selection & Rationale

### Chosen Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Runtime** | **Bun** | 4× faster than Node. Native TypeScript. Built-in test runner. Single binary. |
| **Framework** | **Next.js 16+ (App Router)** | RSC for zero-JS dashboards. API routes as MCP proxy. Streaming. Turbopack stable. |
| **Language** | **TypeScript (strict)** | Complex graph types demand it. Synapse has deep nested models. |
| **Styling** | **Tailwind CSS v4** | Utility-first = terminal precision. No abstraction bloat. |
| **State** | **Zustand** | 1KB. No boilerplate. Perfect for terminal-like command state. |
| **Data Fetching** | **TanStack Query v5** | Cache + stale-while-revalidate for live memory feeds. |
| **Graph Viz** | **D3.js + custom Canvas** | No library wrapping. Raw control for the knowledge graph renderer. |
| **Animations** | **Framer Motion** | Subtle list transitions only. No gratuitous animation. |
| **Fonts** | **JetBrains Mono + SF Mono fallback** | Monospace-first. The terminal IS the brand. |
| **Icons** | **Lucide (tree-shaken)** | Stroke-based, minimal. Matches monospace aesthetic. |
| **Package Manager** | **Bun** | Lockfile + install in <1s. |

### Why NOT Others

| Rejected | Reason |
|----------|--------|
| SvelteKit | Weak graph visualization ecosystem. Fewer production-grade data components. |
| Nuxt/Vue | React ecosystem dominates for data-dense dashboards and D3 integration. |
| Tauri/Electron | Overkill. Synapse is Docker-native. Web-first is correct. |
| Remix | App Router covers its strengths. One fewer abstraction. |
| Vite+React (no framework) | Lose SSR, API routes, streaming. Pain for dashboard use case. |
| CSS-in-JS (styled-components) | Runtime cost. Tailwind compiles to zero JS. Terminal aesthetic = utility classes. |
| Redux/MobX | Overkill for this UI. Zustand is simpler and sufficient. |
| Recharts/Chart.js | Too opinionated for the raw terminal look. D3 gives pixel control. |

---

## 2. Design System — "Terminal Glass"

### 2.1 Color Palette

```
Background:
  --bg-primary:    #0A0A0A    (near-black, not pure black)
  --bg-secondary:  #111111    (card surfaces)
  --bg-tertiary:   #1A1A1A    (hover states, subtle lift)
  --bg-glass:      rgba(17,17,17,0.8)  (frosted panels)

Text:
  --text-primary:  #E8E8E8    (high contrast, not pure white)
  --text-secondary:#888888    (labels, timestamps)
  --text-muted:    #555555    (disabled, decorative)

Memory Layer Accents (the ONLY color in the UI):
  --layer-1-user:       #6366F1  (indigo)     — identity, always present
  --layer-2-procedural: #F59E0B  (amber)      — warm, learned patterns
  --layer-3-semantic:   #10B981  (emerald)     — knowledge, growth
  --layer-4-episodic:   #3B82F6  (blue)       — temporal, flowing
  --layer-5-working:    #EF4444  (red)        — active, session-live

System:
  --accent:        #F8F8F8    (pure white for active focus)
  --border:        #222222    (barely-there borders)
  --success:       #10B981
  --warning:       #F59E0B
  --error:         #EF4444
```

### 2.2 Typography

```
Font Stack:
  --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
  --font-sans: 'Inter', system-ui, sans-serif;  (used ONLY for Thai text fallback)

Scale (modular, 1.25 ratio):
  --text-xs:    11px / 1.5    (timestamps, metadata)
  --text-sm:    13px / 1.5    (body, terminal output)
  --text-base:  14px / 1.6    (primary content)
  --text-lg:    16px / 1.5    (section headers)
  --text-xl:    20px / 1.4    (page titles)

Weight:
  Regular 400 only. Bold 600 for emphasis. Nothing else.
```

### 2.3 Spacing & Layout

```
Grid: 4px base unit
  --space-1:  4px     (inline padding)
  --space-2:  8px     (element gap)
  --space-3:  12px    (group gap)
  --space-4:  16px    (section gap)
  --space-6:  24px    (panel padding)
  --space-8:  32px    (page margin)

Border Radius:
  --radius-sm:  4px   (tags, badges)
  --radius-md:  8px   (cards, inputs)
  --radius-lg:  12px  (modals, panels)

Rule: No radius > 12px. This is a terminal, not a toy.
```

### 2.4 Motion

```
Transitions:
  --ease: cubic-bezier(0.22, 1, 0.36, 1)   (iOS-like spring)
  --duration-fast:   120ms   (hover, focus)
  --duration-normal: 200ms   (panel open/close)
  --duration-slow:   350ms   (page transitions)

Rules:
  - No bounce. No overshoot. Purposeful deceleration only.
  - Lists: stagger 30ms per item, max 5 items animated.
  - Prefer opacity + translateY(4px) for entries.
  - Graph nodes: spring physics at 60fps via Canvas.
```

---

## 3. Layout Architecture

### 3.1 Shell Structure

```
┌──────────────────────────────────────────────────────────────────┐
│  ▸ synapse                              ⌘K  ●  alice   ⚙       │ ← Top Bar (40px)
├────────┬─────────────────────────────────────────────────────────┤
│        │                                                         │
│  feed  │              MAIN CONTENT AREA                          │
│  graph │                                                         │
│  proc  │  (renders current view)                                 │
│  user  │                                                         │
│  sys   │                                                         │
│        │                                                         │
│        │                                                         │
│        │                                                         │
│        │                                                         │
├────────┴─────────────────────────────────────────────────────────┤
│  > _                                                             │ ← Command Bar (36px)
└──────────────────────────────────────────────────────────────────┘
     ↑
  Sidebar (56px collapsed, icons only. 240px expanded on hover)
```

### 3.2 Core Principle: The Feed IS the App

The default view is a **reverse-chronological memory feed** — like a terminal scrolling output.
Every memory event (add, search, decay, consolidation) appears as a feed entry.
This is the heartbeat. You open Synapse and immediately see what your AI memory is doing.

### 3.3 Navigation (5 views, icon-only sidebar)

| Icon | View | Purpose |
|------|------|---------|
| `⊡` | **Feed** | Live memory event stream. Default view. The terminal. |
| `◉` | **Graph** | Knowledge graph explorer. Nodes + edges. Interactive. |
| `▤` | **Procedures** | Layer 2 browser. Trigger → steps. Usage stats. |
| `◈` | **Identity** | User model + preferences. Layer 1 editor. |
| `⚙` | **System** | Health, config, queue status, decay curves. |

No hamburger menus. No dropdowns. Five icons. That's it.

---

## 4. View Specifications

### 4.1 Feed View (Default — "/" route)

The soul of the app. A continuously updating stream of memory events.

```
┌─────────────────────────────────────────────────────────┐
│ ▸ Memory Feed                          ☐ filter  ↻ live │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  12:04:32  ● SEMANTIC  + entity: "React Server Comp…"  │
│            → linked to: "Next.js", "Performance"        │
│            decay: 1.00  ·  access: 0                    │
│                                                         │
│  12:04:30  ● EPISODIC  + episode: "Discussed caching…" │
│            ttl: 90d  ·  source: chat_abc123             │
│                                                         │
│  12:03:58  ● PROCEDURAL  ↑ accessed: "Deploy to Vercel"│
│            success: 12  ·  decay: 0.94                  │
│                                                         │
│  12:01:12  ○ DECAY  ↓ forgotten: "Old API pattern"     │
│            score: 0.09 → archived                       │
│                                                         │
│  11:58:44  ● WORKING  ◇ set: session.current_topic     │
│            value: "frontend architecture"               │
│                                                         │
│  ...                                                    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ > search "react hooks" --layer semantic --limit 10      │
└─────────────────────────────────────────────────────────┘
```

**Feed Entry Anatomy:**
```
[timestamp]  [layer-dot-color]  [LAYER_NAME]  [action-icon]  [action]: [summary]
             [metadata line 1]
             [metadata line 2 — scored/timed values]
```

**Filter chips (top bar):**
`ALL` · `SEMANTIC` · `EPISODIC` · `PROCEDURAL` · `USER` · `WORKING` · `DECAY`

**Live mode:** WebSocket or SSE from MCP server. Green dot = connected.

---

### 4.2 Graph View ("/graph" route)

Full-screen canvas rendering of the knowledge graph from Graphiti/FalkorDB.

```
┌─────────────────────────────────────────────────────────┐
│ ◉ Knowledge Graph          nodes: 1,284  edges: 3,891  │
├────────────┬────────────────────────────────────────────┤
│            │                                            │
│  ◇ Search  │         [  CANVAS AREA  ]                  │
│  ________  │                                            │
│            │      ○ React ──── ○ Hooks                  │
│  Filters:  │        \          |                        │
│  ☑ person  │         ○ Next.js ○ SSR                    │
│  ☑ tech    │           \      /                         │
│  ☑ concept │            ○ Performance                   │
│  ☐ project │              |                             │
│  ☐ topic   │            ○ Caching                       │
│            │                                            │
│  Depth: 2  │                                            │
│  ━━━○━━━━  │                                            │
│            │                                            │
│  Layout:   │                                            │
│  ● force   │                                            │
│  ○ tree    │                                            │
│  ○ radial  │                                            │
│            │                                            │
├────────────┴────────────────────────────────────────────┤
│  └ React (tech)                                        │
│    ├ edges: Hooks, Next.js, Performance                │
│    ├ decay: 0.97  ·  created: 2026-01-15               │
│    └ episodes: 14  ·  community: "Frontend"            │
└─────────────────────────────────────────────────────────┘
         ↑ Detail drawer (bottom, slides up on node click)
```

**Interactions:**
- Click node → detail drawer slides up from bottom
- Drag to pan, scroll to zoom
- Double-click node → expand neighbors (depth+1)
- Right-click → delete edge / delete entity (with confirmation)
- Shift+click → multi-select for batch operations
- Hover → ghost-highlight connected edges

**Node Rendering:**
- Size = access_count (logarithmic scale)
- Opacity = decay_score (0.1–1.0 mapped to 30%–100%)
- Color = entity_type (consistent with layer palette)
- Label = entity name (truncated >20 chars)

**Edge Rendering:**
- Thickness = confidence (0.0–1.0)
- Dashed = superseded edge
- Label on hover = fact/description

---

### 4.3 Procedures View ("/procedures" route)

Layer 2 browser. Table of procedures with expandable rows.

```
┌─────────────────────────────────────────────────────────┐
│ ▤ Procedures                              + Add  ◇ Find│
├─────────────────────────────────────────────────────────┤
│                                                         │
│  trigger              success  decay   topics           │
│  ─────────────────────────────────────────────────       │
│  ▸ Deploy to Vercel       12   0.94   devops, ci        │
│  ▸ Reset Postgres DB       4   0.87   database          │
│  ▸ Thai text preprocess    8   0.91   nlp, thai         │
│  ▾ Setup Docker compose    6   0.82   infra             │
│    ┌─────────────────────────────────────────┐           │
│    │ Steps:                                  │           │
│    │  1. Create docker-compose.yml           │           │
│    │  2. Define services block               │           │
│    │  3. Set environment variables           │           │
│    │  4. Run `docker compose up -d`          │           │
│    │                                         │           │
│    │ Source: chat_xyz789                      │           │
│    │ Created: 2026-02-10  ·  Last used: 3d   │           │
│    │               [Record Success] [Delete] │           │
│    └─────────────────────────────────────────┘           │
│                                                         │
│  ▸ Create API endpoint    3   0.76   backend, api       │
│  ▸ Write unit tests       9   0.93   testing            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Sortable columns:** trigger, success count, decay score, topic
**Actions per row:** Record Success, Edit Steps, Delete
**Add modal:** Trigger (text) → Steps (multiline) → Topics (tags)

---

### 4.4 Identity View ("/identity" route)

Layer 1 user model editor + identity switcher.

```
┌─────────────────────────────────────────────────────────┐
│ ◈ Identity                                              │
├────────────────────┬────────────────────────────────────┤
│                    │                                    │
│  Current Context   │  User Preferences                 │
│  ───────────────   │  ────────────────                  │
│  user:  alice      │  language:  th  ▾                  │
│  agent: claude-3   │  timezone:  Asia/Bangkok           │
│  chat:  abc123     │  response:  concise  ▾             │
│                    │                                    │
│  [Switch User ▾]   │  Expertise:                        │
│  [Clear Agent]     │  ┌──────────────────────┐          │
│  [Clear Chat]      │  │ React · TypeScript ×  │          │
│                    │  │ Docker · Python ×      │          │
│                    │  │ + add...               │          │
│                    │  └──────────────────────┘          │
│                    │                                    │
│                    │  Topics:                           │
│                    │  ┌──────────────────────┐          │
│                    │  │ AI · Memory · NLP ×    │          │
│                    │  │ Frontend · DevOps ×    │          │
│                    │  │ + add...               │          │
│                    │  └──────────────────────┘          │
│                    │                                    │
│                    │  Notes:                            │
│                    │  ┌──────────────────────┐          │
│                    │  │ Prefers dark themes.  │          │
│                    │  │ Works late at night.  │          │
│                    │  └──────────────────────┘          │
│                    │           [Save Changes]           │
│                    │                                    │
└────────────────────┴────────────────────────────────────┘
```

---

### 4.5 System View ("/system" route)

Health dashboard. Minimal. Diagnostic.

```
┌─────────────────────────────────────────────────────────┐
│ ⚙ System                                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Services                    Storage                    │
│  ────────                    ───────                    │
│  MCP Server   ● online       FalkorDB   ● 234 MB       │
│  FalkorDB     ● online       Qdrant     ● 156 MB       │
│  Qdrant       ● online       SQLite     ● 12 MB        │
│  Graphiti     ● online                                  │
│                                                         │
│  Queue                       Memory Stats               │
│  ─────                       ────────────               │
│  Pending:  3                 Entities:   1,284          │
│  Active:   1                 Edges:      3,891          │
│  Failed:   0                 Episodes:   892            │
│  Rate:     10 sem            Procedures: 47             │
│                                                         │
│  Decay Curves                                           │
│  ────────────                                           │
│  ┌──────────────────────────────┐                       │
│  │ 1.0 ┤ ██                     │  ── procedural        │
│  │     ┤  ██                    │  ── semantic           │
│  │ 0.5 ┤   ████                 │  ·· episodic TTL       │
│  │     ┤     ██████             │                        │
│  │ 0.1 ┤──────────████──────────│  ← forget threshold    │
│  │ 0.0 ┤           ████████████ │                        │
│  │     └──────────────────────┘ │                        │
│  │      0d   30d  60d  90d 120d │                        │
│  └──────────────────────────────┘                       │
│                                                         │
│  Config                                                 │
│  ──────                                                 │
│  LLM: anthropic / claude-3-5-sonnet                     │
│  Embedder: paraphrase-multilingual-MiniLM-L12-v2        │
│  Semaphore: 10                                          │
│  Transport: http / :47780                               │
│                                                         │
│             [Run Decay Maintenance]  [Clear Graph ⚠]    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Command Bar — The Core Interaction

Always present at the bottom. `⌘K` or `/` to focus.

```
> _
```

**This is the power-user layer.** Everything has a GUI, but everything can also be typed.

### Command Grammar

```
> search <query> [--layer <layer>] [--limit <n>]
> add <content> [--layer <layer>] [--source <source>]
> identity set <user_id> [<agent_id>] [<chat_id>]
> identity clear
> procedure add <trigger> --steps "1. ... 2. ..."
> procedure success <trigger>
> consult <query>
> reflect [--layer <layer>]
> analyze <type: topics|procedures|activity> [--days <n>]
> consolidate [--dry-run] [--min-access <n>]
> status
> clear graph --confirm
> delete <entity|edge|episode> <uuid>
```

**Autocomplete:** Fuzzy match against commands + entity names. Tab to accept.
**History:** ↑/↓ arrows. Persisted in localStorage.
**Output:** Result renders inline in the feed, highlighted with a blue-left-border.

---

## 6. API Layer (FastAPI Backend)

**⚠️ ARCHITECTURE CHANGE:** Next.js no longer has API routes. Frontend calls FastAPI Gateway directly.

```
Browser  →  Next.js (UI only)  →  FastAPI Gateway (:8000)  →  SynapseService
                                         ↓
                                    FalkorDB / Qdrant / SQLite
```

### FastAPI Endpoints (39 total)

See `docs/plans/backend_api_plan.md` for full specification.

### API Client (Frontend)

```typescript
// lib/api-client.ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = {
  // Memory
  memory: {
    list: (params) => fetch(`${API_BASE}/api/memory?${params}`),
    get: (id) => fetch(`${API_BASE}/api/memory/${id}`),
    add: (data) => fetch(`${API_BASE}/api/memory`, { method: 'POST', body: JSON.stringify(data) }),
    search: (query) => fetch(`${API_BASE}/api/memory/search`, { method: 'POST', body: JSON.stringify({ query }) }),
  },
  // Graph
  graph: {
    nodes: (params) => fetch(`${API_BASE}/api/graph/nodes?${params}`),
    node: (id) => fetch(`${API_BASE}/api/graph/nodes/${id}`),
    edges: (id) => fetch(`${API_BASE}/api/graph/nodes/${id}/edges`),
  },
  // Feed
  feed: {
    recent: () => fetch(`${API_BASE}/api/feed`),
    stream: () => new EventSource(`${API_BASE}/api/feed/stream`),
  },
  // ... etc
};
```

### Types (Frontend)

```
lib/
├── api-client.ts         // HTTP client to FastAPI
├── types/
│   ├── memory.ts         // Memory layer types
│   ├── graph.ts          // Node, Edge, Episode types
│   ├── identity.ts       // UserContext, Identity types
│   └── system.ts         // Status, Config types
└── hooks/
    ├── use-feed.ts       // SSE subscription + feed state
    ├── use-graph.ts      // Graph data fetching + layout
    ├── use-command.ts    // Command bar parsing + execution
    └── use-identity.ts   // Current identity context
```

---

## 7. Project Structure

```
synapse-ui/
├── bun.lock
├── next.config.ts
├── package.json
├── tailwind.config.ts
├── tsconfig.json
├── postcss.config.ts
├── .env.local                   # MCP_SERVER_URL=http://localhost:47780
│
├── public/
│   └── fonts/
│       └── JetBrainsMono-*.woff2
│
├── app/
│   ├── layout.tsx               # Shell: sidebar + command bar + fonts
│   ├── page.tsx                 # Feed view (default)
│   ├── graph/
│   │   └── page.tsx             # Graph explorer
│   ├── procedures/
│   │   └── page.tsx             # Procedure browser
│   ├── identity/
│   │   └── page.tsx             # Identity & preferences
│   ├── system/
│   │   └── page.tsx             # Health dashboard
│   ├── globals.css              # Tailwind directives + CSS variables
│   └── api/                     # (see section 6)
│
├── components/
│   ├── shell/
│   │   ├── sidebar.tsx          # 56px icon rail
│   │   ├── top-bar.tsx          # Title + identity badge + settings
│   │   └── command-bar.tsx      # Bottom command input + autocomplete
│   ├── feed/
│   │   ├── feed-list.tsx        # Virtualized event list
│   │   ├── feed-entry.tsx       # Single event row
│   │   ├── feed-filters.tsx     # Layer filter chips
│   │   └── feed-search-result.tsx  # Inline search result card
│   ├── graph/
│   │   ├── graph-canvas.tsx     # D3 force-directed canvas renderer
│   │   ├── graph-controls.tsx   # Filter panel + depth slider
│   │   ├── graph-detail.tsx     # Bottom drawer for node details
│   │   └── graph-search.tsx     # Entity search input
│   ├── procedures/
│   │   ├── procedure-table.tsx  # Sortable table
│   │   ├── procedure-row.tsx    # Expandable row
│   │   └── procedure-form.tsx   # Add/edit modal
│   ├── identity/
│   │   ├── identity-card.tsx    # Current context display
│   │   ├── preferences-form.tsx # User preferences editor
│   │   └── tag-input.tsx        # Expertise/topic tag editor
│   ├── system/
│   │   ├── service-status.tsx   # Service health grid
│   │   ├── memory-stats.tsx     # Entity/edge/episode counts
│   │   ├── decay-chart.tsx      # D3 decay curve visualization
│   │   └── config-display.tsx   # Read-only config viewer
│   └── ui/
│       ├── badge.tsx            # Layer color badge
│       ├── button.tsx           # Minimal button variants
│       ├── chip.tsx             # Filter chip
│       ├── drawer.tsx           # Slide-up panel
│       ├── input.tsx            # Monospace input
│       ├── modal.tsx            # Centered dialog
│       ├── spinner.tsx          # Dots-based loading indicator
│       └── tooltip.tsx          # Minimal tooltip
│
├── lib/
│   ├── mcp-client.ts
│   ├── command-parser.ts        # Parse command bar input
│   ├── constants.ts             # Layer colors, names, icons
│   ├── utils.ts                 # Formatters, classnames
│   ├── types/
│   │   ├── memory.ts
│   │   ├── graph.ts
│   │   ├── identity.ts
│   │   └── system.ts
│   ├── hooks/
│   │   ├── use-feed.ts
│   │   ├── use-graph.ts
│   │   ├── use-command.ts
│   │   └── use-identity.ts
│   └── stores/
│       ├── feed-store.ts        # Zustand: feed entries + filters
│       ├── graph-store.ts       # Zustand: selected node, zoom, layout
│       └── command-store.ts     # Zustand: history, autocomplete
│
├── Dockerfile
└── docker-compose.yml           # Extends parent compose for dev
```

---

## 8. Implementation Phases

> **Detailed Plans:** See `phase-1-foundation.md`, `phase-2-graph.md`, `phase-3-crud.md`, `phase-4-polish.md`
> **Quality Gates:** See `quality-gates-overview.md`
> **Roadmap:** See `ROADMAP.md`

### Phase 1 — Foundation (Shell + Feed)

**Goal:** Open the app and see a live memory feed in a terminal-like interface.

| Task | Details |
|------|---------|
| Scaffold Next.js 16+ with Bun | `bun create next-app synapse-ui --ts --tailwind --app --src-dir=false --turbopack` |
| Design system setup | Tailwind config: colors, fonts, spacing as defined in §2 |
| Shell layout | Sidebar (icons) + Top bar + Command bar + Content area |
| MCP client library | Typed HTTP client wrapping all 25+ MCP tools |
| Feed view | SSE/polling stream → virtualized list → styled entries |
| Command bar (basic) | Text input, parse `search` and `status` commands |
| Identity display | Show current user/agent/chat in top bar |

**Deliverable:** Working app showing real memory events from a running Synapse instance.

### Phase 2 — Graph Explorer

**Goal:** Interactive knowledge graph visualization.

| Task | Details |
|------|---------|
| Canvas renderer | D3 force-directed graph on HTML5 Canvas (not SVG — performance) |
| Node/edge fetch | API routes wrapping `search_nodes`, `get_entity_edge` |
| Interaction layer | Click, drag, zoom, expand neighbors |
| Detail drawer | Bottom sheet with entity details, connected edges, episodes |
| Entity type filters | Checkbox panel for person/tech/concept/project/topic |
| Depth control | Slider to expand graph traversal depth |

**Deliverable:** Navigate and understand the entire knowledge graph visually.

### Phase 3 — Procedures + Identity

**Goal:** Full CRUD for Layer 2 procedures and Layer 1 user preferences.

| Task | Details |
|------|---------|
| Procedure table | Sortable, expandable rows |
| Add procedure form | Modal with trigger, steps, topics |
| Record success action | One-click success recording |
| Identity switcher | Dropdown to switch user context |
| Preferences editor | Form for language, timezone, expertise tags, topics, notes |
| Tag input component | Add/remove tags with autocomplete |

**Deliverable:** Manage procedures and user identity without terminal commands.

### Phase 4 — System + Oracle + Polish

**Goal:** System dashboard, oracle tools, and production polish.

| Task | Details |
|------|---------|
| Service health grid | Ping `get_status`, display per-service status |
| Memory statistics | Live counts for entities, edges, episodes, procedures |
| Decay curve chart | D3 line chart showing decay formulas over time |
| Oracle commands | `consult`, `reflect`, `analyze` in command bar + dedicated UI |
| Consolidation UI | Dry-run preview → confirm → execute |
| Command bar complete | All commands, autocomplete, history, keyboard navigation |
| Error handling | Toast notifications, retry logic, offline state |
| Thai text rendering | Ensure monospace + Thai fallback font works correctly |
| Responsive breakpoints | Sidebar collapses on mobile, feed full-width |
| Docker integration | Dockerfile + compose service extending parent stack |

**Deliverable:** Production-ready management dashboard.

---

## 9. Key UX Decisions

| Decision | Rationale |
|----------|-----------|
| **Feed-first, not dashboard-first** | Dashboards are glanced at, feeds are lived in. Memory is temporal. |
| **Command bar always visible** | Power users type faster than they click. The terminal aesthetic demands it. |
| **No color except layer accents** | Monochrome + 5 accent colors = instant layer recognition. No cognitive overload. |
| **No pagination, virtualized scroll** | Terminal doesn't paginate. It scrolls. Virtualization keeps it fast. |
| **Canvas graph, not SVG** | 1000+ nodes need 60fps. SVG chokes at ~300 nodes. Canvas + WebGL fallback. |
| **Bottom detail drawer, not sidebar** | Sidebar is navigation. Details are contextual. iOS pattern: sheet from bottom. |
| **Monospace everything** | Data alignment. Terminal feel. Scannable. The font IS the design. |
| **No onboarding/empty states** | If Synapse is running, there's data. If not, show connection error. No hand-holding. |
| **Destructive actions need `--confirm`** | CLI pattern. `clear graph` needs `clear graph --confirm`. Always. |
| **SSE over WebSocket** | Simpler. HTTP-compatible. No connection state to manage. Auto-reconnect built-in. |

---

## 10. Performance Targets

| Metric | Target |
|--------|--------|
| First Contentful Paint | < 800ms |
| Feed entry render | < 16ms (60fps scroll) |
| Graph render (1000 nodes) | 60fps on Canvas |
| Command autocomplete | < 50ms response |
| Memory search (via MCP) | < 500ms end-to-end |
| Bundle size (gzipped) | < 120KB JS first load |
| Lighthouse score | > 95 (Performance) |

---

## 11. Dependencies (package.json)

```json
{
  "dependencies": {
    "next": "^16.0",
    "react": "^19.0",
    "react-dom": "^19.0",
    "zustand": "^5.0",
    "@tanstack/react-query": "^5.60",
    "d3-force": "^3.0",
    "d3-scale": "^4.0",
    "d3-shape": "^3.0",
    "framer-motion": "^12.0",
    "lucide-react": "^0.470",
    "clsx": "^2.1",
    "tailwind-merge": "^3.0"
  },
  "devDependencies": {
    "typescript": "^5.7",
    "tailwindcss": "^4.0",
    "@tailwindcss/postcss": "^4.0",
    "@types/d3-force": "^3.0",
    "@types/d3-scale": "^4.0",
    "@types/d3-shape": "^3.0",
    "@types/react": "^19.0",
    "@types/react-dom": "^19.0"
  }
}
```

---

## 12. Docker Integration

```yaml
# synapse-ui/docker-compose.yml
services:
  synapse-ui:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - MCP_SERVER_URL=http://synapse:47780
    depends_on:
      synapse:
        condition: service_healthy
    networks:
      - synapse-network

networks:
  synapse-network:
    external: true
```

---

## Summary

**Stack:** Bun + Next.js 16+ + TypeScript + Tailwind v4 + D3 + Zustand

**Design:** Dark monospace terminal. 5 layer-accent colors. Feed-first. Command bar.

**Views:** Feed → Graph → Procedures → Identity → System

**Communication:** Next.js API Routes → MCP Server HTTP

**Phases:** 4 phases. Shell+Feed first. Graph second. CRUD third. Polish fourth.
