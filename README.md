<p align="center">
  <img src="docs/assets/synapse-logo.svg" alt="Synapse Logo" width="200" height="200">
</p>

<h1 align="center">Synapse</h1>

<p align="center">
  <strong>One Brain. Infinite Connections.</strong>
</p>

<p align="center">
  Unified AI Memory System — Knowledge Graph + Five-Layer Memory + Thai NLP
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#documentation">Docs</a> •
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/release/python-3120/">
    <img src="https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white" alt="Python Version">
  </a>
  <a href="https://github.com/getzep/graphiti">
    <img src="https://img.shields.io/badge/Graphiti-0.28%2B-green?logo=data:image/png;base64" alt="Graphiti Version">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-Apache%202.0-purple?logo=opensourceinitiative&logoColor=white" alt="License">
  </a>
  <a href="https://github.com/features/actions">
    <img src="https://img.shields.io/badge/Status-Phase%205%20M2%20Complete-brightgreen?logo=github" alt="Project Status">
  </a>
</p>

---

## Overview

Synapse is a **production-ready AI memory system** forked from [Graphiti](https://github.com/getzep/graphiti) with enhanced capabilities from [Oracle-v2](https://github.com/Soul-Brews-Studio/oracle-v2):

| From Graphiti (Base) | From Oracle-v2 (Enhanced) |
|---------------------|---------------------------|
| ✅ Temporal Knowledge Graph | ✅ Five-Layer Memory Model |
| ✅ Entity Extraction | ✅ Thai NLP Integration |
| ✅ Contradiction Handling | ✅ User Model (preferences, expertise) |
| ✅ Hybrid Retrieval | ✅ Procedural Memory (how-to patterns) |
| ✅ MCP Server Built-in | ✅ Decay Scoring System |
| ✅ Provenance (Episodes) | ✅ TTL-based Episodic Memory |

---

## Features

### 🧠 Five-Layer Memory System

Human-inspired memory architecture with automatic decay:

| Layer | Purpose | Decay | Storage |
|-------|---------|-------|---------|
| **User Model** | Preferences, expertise | Never | SQLite |
| **Procedural** | How-to patterns | Slow (λ=0.005, ~139 days) | SQLite + FTS5 |
| **Semantic** | Principles, learnings | Normal (λ=0.01, ~69 days) | Graphiti |
| **Episodic** | Conversation summaries | TTL (90 days, +30 on access) | SQLite + FTS5 |
| **Working** | Session context | Session only | In-memory |

### 🇹🇭 Thai NLP Integration

Full Thai language support with graceful fallbacks:

- **Language Detection** - Thai/English/Mixed with confidence scores
- **Word Tokenization** - pythainlp (newmm) with regex fallback
- **Text Normalization** - Fix common Thai typos (เเ → แ)
- **Spell Checking** - Thai spell correction
- **Stopword Removal** - Built-in + pythainlp corpus

### 🔌 MCP Server

20+ MCP tools for AI assistants:

<details>
<summary><strong>Memory Tools</strong></summary>

| Tool | Description |
|------|-------------|
| `synapse_remember` | Add memory (auto layer detect) |
| `synapse_recall` | Search memories (hybrid) |
| `synapse_forget` | Decay/archive/delete |
| `synapse_context` | Get user context |

</details>

<details>
<summary><strong>Graph Tools</strong></summary>

| Tool | Description |
|------|-------------|
| `synapse_query` | Graph traversal |
| `synapse_timeline` | Temporal queries |
| `synapse_entities` | Manage entities |
| `synapse_relations` | Manage relationships |

</details>

<details>
<summary><strong>Thai NLP Tools</strong></summary>

| Tool | Description |
|------|-------------|
| `detect_language` | Detect Thai/English/Mixed |
| `preprocess_for_extraction` | Normalize for entity extraction |
| `preprocess_for_search` | Tokenize for FTS5 search |
| `tokenize_thai` | Word segmentation |
| `normalize_thai` | Fix typos, remove zero-width |
| `is_thai_text` | Quick Thai check |

</details>

---

## Quick Start

### Prerequisites

- Python 3.12+
- Docker (for FalkorDB)
- Optional: [pythainlp](https://github.com/PyThaiNLP/pythainlp) for Thai NLP

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/synapse.git
cd synapse

# Start FalkorDB (Redis-based graph database)
docker run -d --name falkordb -p 6379:6379 -p 3000:3000 falkordb/falkordb

# Install with Thai NLP support
pip install -e ".[thai]"

# Or install minimal
pip install -e .
```

### Run MCP Server

```bash
# Using the CLI
synapse-mcp

# Or directly
cd synapse/mcp_server && python -m graphiti_mcp_server

# With custom config
synapse-mcp --config config.yaml --transport http --port 47780
```

### Python Usage

```python
from synapse.nlp import detect_language, preprocess_for_search
from synapse.layers import get_layer_manager

# Detect language
result = detect_language("สวัสดีครับ Hello World")
print(f"Language: {result.language}, Thai ratio: {result.thai_ratio:.2f}")

# Preprocess for search
query = preprocess_for_search("ค้นหาเกี่ยวกับ machine learning")
# → "ค้น หา เกี่ยว กับ machine learning"

# Use layer manager
manager = get_layer_manager()

# Record episode
episode = manager.record_episode(
    content="User asked about Rust async patterns",
    summary="Discussed tokio::select! and async channels",
    topics=["rust", "async", "tokio"],
    outcome="success"
)

# Find procedures
procedures = manager.find_procedures("git commit")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (Port 47780)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Memory      │  │ Graph       │  │ Thai NLP                │  │
│  │ • remember  │  │ • query     │  │ • detect_language       │  │
│  │ • recall    │  │ • timeline  │  │ • preprocess_for_search │  │
│  │ • forget    │  │ • entities  │  │ • tokenize_thai         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Engine                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Layer Manager   │  │ Graphiti Core   │  │ Thai NLP        │  │
│  │ (5 layers)      │  │ (temporal KG)   │  │ (router/preproc)│  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ FalkorDB    │  │ Qdrant      │  │ SQLite                  │  │
│  │ (Graph)     │  │ (Vector)    │  │ (User/Proc/Episodic)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
synapse/
├── synapse/
│   ├── layers/              # Five-layer memory system
│   │   ├── types.py         # Enums, models, dataclasses
│   │   ├── decay.py         # Decay scoring, TTL computation
│   │   ├── user_model.py    # Layer 1: Never-decaying preferences
│   │   ├── procedural.py    # Layer 2: How-to patterns
│   │   ├── semantic.py      # Layer 3: Knowledge graph
│   │   ├── episodic.py      # Layer 4: Conversation summaries
│   │   ├── working.py       # Layer 5: Session context
│   │   └── manager.py       # Unified layer manager
│   │
│   ├── nlp/                 # Thai NLP integration
│   │   ├── thai.py          # ThaiDetector, ThaiTokenizer, etc.
│   │   ├── router.py        # LanguageRouter, LanguageDetector
│   │   └── preprocess.py    # TextPreprocessor for extraction/search
│   │
│   ├── graphiti/            # Vendored Graphiti code
│   │
│   └── mcp_server/          # MCP server implementation
│       └── src/
│           ├── graphiti_mcp_server.py
│           └── thai_nlp_tools.py
│
├── tests/                   # Test suite
├── docs/                    # Documentation
│   ├── PROJECT_PLAN.md      # Full architecture + timeline
│   ├── DECISION_LOG.md      # Why we chose this approach
│   ├── QUICK_REFERENCE.md   # One-page summary
│   ├── reports/             # Phase completion reports
│   └── reviews/             # Codex security reviews
│
├── pyproject.toml           # Package configuration
└── README.md
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Project Plan](./docs/PROJECT_PLAN.md) | Full architecture + 5-phase timeline |
| [Decision Log](./docs/DECISION_LOG.md) | Technical decisions and rationale |
| [Quick Reference](./docs/QUICK_REFERENCE.md) | One-page developer summary |
| [Phase Reports](./docs/reports/) | Completion reports for each phase |
| [Security Reviews](./docs/reviews/) | Codex security audit results |

---

## Development

### Setup

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_layers.py -v

# Type checking
mypy synapse/
```

### Adding New Memory Layers

```python
from synapse.layers import MemoryLayer, SynapseNode

class CustomLayer:
    """Custom memory layer implementation."""

    LAYER_TYPE = MemoryLayer.SEMANTIC
    DECAY_LAMBDA = 0.01  # Normal decay

    def add(self, content: str, **metadata) -> SynapseNode:
        # Implement storage logic
        pass

    def search(self, query: str, limit: int = 10) -> List[SynapseNode]:
        # Implement retrieval logic
        pass
```

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | Core setup, types, Graphiti integration |
| Phase 2 | ✅ Complete | Vendored Graphiti, MCP server |
| Phase 3 | ✅ Complete | Five-Layer Memory System |
| Phase 4 | ✅ Complete | Thai NLP Integration |
| Phase 5 | 🚧 In Progress | Deploy as Memory Backend for Cerberus |

### Phase 5 Progress

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1 Smoke Test | ✅ Complete | Basic functionality verified |
| M2 MCP Integration | ✅ Complete | Anthropic LLM + Local Embedder + BGE Reranker |
| M3 Production Deploy | ⏳ Pending | Docker Compose + Production Config |

---

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [Graphiti](https://github.com/getzep/graphiti) by [Zep](https://www.getzep.com/) - Base temporal knowledge graph framework
- [Oracle-v2](https://github.com/Soul-Brews-Studio/oracle-v2) - Five-layer memory model inspiration
- [PyThaiNLP](https://github.com/PyThaiNLP/pythainlp) - Thai language processing library

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/b9b4ymiN">Boat</a> & <a href="https://anthropic.com">Claude</a>
</p>
