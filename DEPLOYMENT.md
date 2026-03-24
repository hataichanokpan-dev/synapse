# Synapse Production Deployment Guide

> **Version**: 1.0.0
> **Date**: 2026-03-20
> **Status**: Setup guide only. Use the current release gate below for go/no-go decisions.

---

## Current Release Gate

The canonical production gate is:

- [docs/checklists/production_release_checklist_2026-03-20.md](docs/checklists/production_release_checklist_2026-03-20.md)
- `python scripts/pre_deploy_smoke.py --base-url <url> --api-key <key> --output-json artifacts/pre_deploy_smoke.json`

Do not rely on historical QA scores in this file as a release decision.

---

## Prerequisites

### Required Services
- [x] FalkorDB (Redis Graph) - Port 6379
- [x] Qdrant (Vector DB) - Port 6333
- [x] Anthropic API Key (or OpenAI)

### Python Requirements
- Python 3.12+
- See `requirements.txt`

---

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://api.anthropic.com  # or custom endpoint

# Optional
SYNAPSE_REQUIRE_GRAPHITI=false  # Set to 'true' for fail-fast mode
SYNAPSE_ENABLE_GRAPHITI=true    # Set to 'false' for SQLite-only / no-graph mode
SYNAPSE_ENABLE_QDRANT=true      # Set to 'false' for SQLite-only / no-vector mode
FALKORDB_URI=redis://localhost:6379
FALKORDB_PASSWORD=
```

---

## Quick Deploy

### Option 1: Docker Compose (Recommended)

```bash
# Start services
docker-compose up -d

# Run Synapse
python -m synapse.mcp_server
```

### Frontend UI in Docker

The Next.js frontend can run in Docker on `http://localhost:7533`.

```bash
# Build and start backend + frontend
docker compose up -d --build falkordb qdrant synapse-api synapse-ui
```

Default ports:
- UI: `7533`
- API: `8000`
- FalkorDB: `6379`
- Qdrant: `6333`

Environment notes:
- `synapse-ui` builds with `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8000`
- if you change the API host/port, also set `NEXT_PUBLIC_API_URL` before `docker compose up --build`
- the frontend uses the same API key as `SYNAPSE_API_KEY` by default

### Option 2: Manual Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start FalkorDB
docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest

# 3. Start Qdrant (optional)
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest

# 4. Copy .env file
cp .env.example .env
# Edit .env with your API keys

# 5. Run tests
pytest tests/ -v

# 6. Start server
python -m synapse.mcp_server
```

---

## Production Checklist

- [x] All unit tests pass (90/90)
- [x] Layer 3 integration tests pass (10/11)
- [x] Graphiti writes to FalkorDB
- [x] Entity extraction works
- [x] Error handling implemented
- [x] Health checks working
- [x] Environment variables documented
- [ ] CI/CD pipeline (manual setup required)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Synapse MCP Server                    │
├─────────────────────────────────────────────────────────┤
│  Layer 1: User Model      │ SQLite (~/.synapse/)        │
│  Layer 2: Procedural       │ SQLite + Vector            │
│  Layer 3: Semantic/Graph   │ FalkorDB (Graph)           │
│  Layer 4: Episodic         │ SQLite + Qdrant           │
│  Layer 5: Working Memory   │ In-Memory                  │
├─────────────────────────────────────────────────────────┤
│  Oracle Tools: consult, reflect, analyze, consolidate    │
└─────────────────────────────────────────────────────────┘
```

---

## Monitoring

### Health Check Endpoint
```python
# GET /health
{
  "status": "healthy",
  "components": {
    "graphiti": "ok",
    "qdrant": "ok",
    "layers": "ok"
  }
}
```

---

## Troubleshooting

### Common Issues

1. **Graphiti connection fails**
   - Check FalkorDB is running: `docker ps | grep falkordb`
   - Check port 6379 is open

2. **Entity extraction fails**
   - Verify ANTHROPIC_API_KEY is set
   - Check API quota

3. **Group ID validation error**
   - Use alphanumeric, dashes, underscores only
   - Default: "default"

---

## Support

- GitHub Issues: [project-url]/issues
- Documentation: README.md
