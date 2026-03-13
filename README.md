# Synapse

> **"One Brain. Infinite Connections."**

Unified AI Memory System - Knowledge Graph + Five-Layer Memory + Thai NLP

## Overview

Synapse is a fork of [Graphiti](https://github.com/getzep/graphiti) with Oracle-v2 features injected:

**From Graphiti (Free):**
- Temporal Knowledge Graph
- Entity extraction
- Contradiction handling
- Hybrid retrieval (semantic + BM25 + graph)
- MCP Server built-in
- Provenance (Episodes)

**From Oracle-v2 (Added):**
- Five-Layer Memory Model
- Thai NLP Sidecar
- User Model (preferences, expertise)
- Procedural Memory (how-to patterns)
- Decay Scoring System

## Quick Start

```bash
# Clone
git clone https://github.com/getzep/graphiti synapse
cd synapse

# Setup FalkorDB
docker run -d -p 6379:6379 -p 3000:3000 falkordb/falkordb

# Install
pip install -e ".[dev]"

# Run MCP Server
cd mcp_server && python -m graphiti_mcp_server
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              MCP Server (Port 47780)         │
├─────────────────────────────────────────────┤
│  Memory Layer    │  Graph Layer  │  System  │
│  ─────────────   │  ────────────  │  ──────  │
│  • remember      │  • query       │  • stats │
│  • recall        │  • timeline    │  • health│
│  • forget        │  • entities    │  • backup│
│  • context       │  • relations   │          │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│              Core Engine                     │
├─────────────────────────────────────────────┤
│  Layer Engine │ Graph Engine │ Thai NLP     │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│              Storage Layer                   │
├─────────────────────────────────────────────┤
│  FalkorDB (Graph) │ ChromaDB │ SQLite       │
└─────────────────────────────────────────────┘
```

## Five-Layer Memory

| Layer | Purpose | Decay |
|-------|---------|-------|
| 1. user_model | Preferences, expertise | Never |
| 2. procedural | How-to patterns | Slow (139 days) |
| 3. semantic | Principles, learnings | Normal (69 days) |
| 4. episodic | Conversation summaries | TTL 90 days |
| 5. working | Session context | Session only |

## MCP Tools

### Memory
- `synapse_remember` - Add memory (auto layer detect)
- `synapse_recall` - Search memories (hybrid)
- `synapse_forget` - Decay/archive/delete
- `synapse_context` - Get user context

### Graph
- `synapse_query` - Graph traversal
- `synapse_timeline` - Temporal queries
- `synapse_entities` - Manage entities
- `synapse_relations` - Manage relationships

### User
- `synapse_profile` - User profile CRUD
- `synapse_preferences` - Preferences CRUD

## Project Structure

```
synapse/
├── synapse/                 # Our additions
│   ├── layers/              # Five-layer memory
│   │   ├── __init__.py
│   │   ├── types.py
│   │   ├── decay.py
│   │   ├── user_model.py
│   │   ├── procedural.py
│   │   ├── semantic.py
│   │   └── episodic.py
│   │
│   ├── nlp/                 # Thai NLP
│   │   ├── __init__.py
│   │   ├── thai.py
│   │   └── detector.py
│   │
│   ├── mcp/                 # Extended MCP tools
│   │   ├── __init__.py
│   │   ├── tools.py
│   │   └── server.py
│   │
│   └── storage/             # Storage clients
│       ├── __init__.py
│       ├── falkordb.py
│       └── sqlite.py
│
├── graphiti/                # Original Graphiti (from fork)
├── mcp_server/              # Graphiti MCP (from fork)
│
├── tests/
├── docs/
├── scripts/
│
├── pyproject.toml
└── README.md
```

## Documentation

- [Project Plan](./docs/PROJECT_PLAN.md) - Full architecture + timeline
- [Decision Log](./docs/DECISION_LOG.md) - Why we chose this approach
- [Quick Reference](./docs/QUICK_REFERENCE.md) - One-page summary

## License

Apache 2.0 (from Graphiti)

## Credits

- [Graphiti](https://github.com/getzep/graphiti) by Zep - Base framework
- [Oracle-v2](https://github.com/Soul-Brews-Studio/oracle-v2) - Five-layer model + Thai NLP
