# Using Synapse MCP in Claude Code

> คู่มือการใช้งาน Synapse MCP Server กับ Claude Code (Docker Deployment)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code                               │
│                    (MCP Client over HTTP)                        │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTP :47780
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Synapse MCP │  │ FalkorDB    │  │ Qdrant                  │  │
│  │ Port 47780  │  │ Port 6379   │  │ Port 6333              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Prerequisites

- Docker & Docker Compose
- Claude Code CLI
- API Key (ANTHROPIC_API_KEY หรือ OPENAI_API_KEY)

---

## 2. Docker Deployment

### 2.1 Clone & Configure

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/synapse.git
cd synapse

# Create .env file
cat > .env << 'EOF'
# Required - LLM API
ANTHROPIC_API_KEY=sk-ant-xxx

# Optional - Database ports (defaults shown)
FALKORDB_PORT=6379
QDRANT_HTTP_PORT=6333
QDRANT_GRPC_PORT=6334
SYNAPSE_PORT=47780

# Optional - Performance
SEMAPHORE_LIMIT=10
EOF
```

### 2.2 Build & Run

```bash
# Build and start all services
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f synapse
```

### 2.3 Verify Deployment

```bash
# Health check
curl http://localhost:47780/health

# Expected response
{"status": "healthy", "service": "graphiti-mcp"}
```

### 2.4 Verify MCP Tools

```bash
# Quick Python test
python -c "
import asyncio, json, httpx

async def test():
    url = 'http://localhost:47780/mcp/'
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream'
    }

    async with httpx.AsyncClient(timeout=30) as client:
        # Initialize
        resp = await client.post(url, json={
            'jsonrpc': '2.0',
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'test', 'version': '1.0'}
            },
            'id': 1
        }, headers=headers)

        session_id = resp.headers.get('mcp-session-id')
        headers['Mcp-Session-Id'] = session_id

        # Get tools
        resp = await client.post(url, json={
            'jsonrpc': '2.0',
            'method': 'tools/list',
            'params': {},
            'id': 2
        }, headers=headers)

        for line in resp.text.split('\n'):
            if line.startswith('data: '):
                data = json.loads(line[6:])
                tools = data.get('result', {}).get('tools', [])
                print(f'✅ MCP Server working! Found {len(tools)} tools')
                break

asyncio.run(test())
"
```

### 2.5 Management Commands

```bash
# Stop all services
docker compose down

# Stop and remove volumes (clean slate)
docker compose down -v

# Restart synapse only
docker compose restart synapse

# View resource usage
docker stats synapse-server
```

---

## 3. Claude Code Configuration

### 3.1 Add to settings.json

เปิด `~/.claude/settings.json` และเพิ่ม:

```json
{
  "mcpServers": {
    "synapse": {
      "type": "http",
      "url": "http://localhost:47780/mcp/"
    }
  }
}
```

### 3.2 With Authentication (Optional)

```json
{
  "mcpServers": {
    "synapse": {
      "type": "http",
      "url": "http://localhost:47780/mcp/",
      "headers": {
        "Authorization": "Bearer your-token-here"
      }
    }
  }
}
```

### 3.3 Remote Server

```json
{
  "mcpServers": {
    "synapse": {
      "type": "http",
      "url": "http://your-server:47780/mcp/"
    }
  }
}
```

---

## 4. Available MCP Tools

> **31 MCP Tools** available across 7 categories

### 4.1 Thai NLP Tools (6)

| Tool | Description | Parameters |
|------|-------------|------------|
| `detect_language` | ตรวจจับภาษา (Thai/English/Mixed) | `text` |
| `preprocess_for_extraction` | เตรียมข้อความสำหรับ entity extraction | `text` |
| `preprocess_for_search` | เตรียมข้อความสำหรับค้นหา | `text` |
| `tokenize_thai` | ตัดคำภาษาไทย | `text` |
| `normalize_thai` | ปรับข้อความไทยให้ถูกต้อง | `text` |
| `is_thai_text` | ตรวจสอบว่าเป็นภาษาไทยหรือไม่ | `text` |

### 4.2 Memory Tools (4)

| Tool | Description | Parameters |
|------|-------------|------------|
| `add_memory` | เพิ่มความจำใหม่ | `name`, `episode_body`, `source_description?`, `group_ids?` |
| `search_nodes` | ค้นหา nodes ใน graph | `query`, `group_ids?`, `max_results?` |
| `search_memory_facts` | ค้นหา facts | `query`, `group_ids?`, `max_results?` |
| `search_memory_layers` | ค้นหาใน layers | `query`, `layers?`, `max_results?` |

### 4.3 User Model Tools (2)

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_user_preferences` | ดึง preferences | `user_id?` |
| `update_user_preferences` | อัปเดต preferences | `language?`, `response_style?`, `expertise_areas?` |

### 4.4 Procedural Memory Tools (3)

| Tool | Description | Parameters |
|------|-------------|------------|
| `find_procedures` | ค้นหา procedures | `trigger`, `limit?` |
| `add_procedure` | เพิ่ม procedure | `trigger`, `steps`, `tags?` |
| `record_procedure_success` | บันทึกสำเร็จ | `procedure_id` |

### 4.5 Working Memory Tools (3)

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_working_context` | ดึง context | `key?`, `default?` |
| `set_working_context` | เก็บ context | `key`, `value`, `ttl_seconds?` |
| `clear_working_context` | ล้าง context | `key?` |

### 4.6 Identity Tools (3)

| Tool | Description | Parameters |
|------|-------------|------------|
| `set_identity` | ตั้งค่า identity | `user_id?`, `agent_id?`, `chat_id?` |
| `get_identity` | ดึง identity | - |
| `clear_identity` | ล้าง identity | - |

### 4.7 Oracle Tools (4)

| Tool | Description | Parameters |
|------|-------------|------------|
| `synapse_consult` | ปรึกษาความจำ | `query`, `layers?`, `context?` |
| `synapse_reflect` | สุ่ม reflection | `layer?` |
| `synapse_analyze` | วิเคราะห์ patterns | `analysis_type?`, `time_range_days?` |
| `synapse_consolidate` | ย้ายระหว่าง layers | `source`, `min_access_count?` |

### 4.8 Graph Management Tools (6)

| Tool | Description | Parameters |
|------|-------------|------------|
| `delete_entity_edge` | ลบ edge | `uuid` |
| `delete_episode` | ลบ episode | `uuid` |
| `get_entity_edge` | ดึง edge | `uuid` |
| `get_episodes` | ดึง episodes | `group_ids?`, `max_episodes?` |
| `clear_graph` | ล้าง graph | `group_ids?` |
| `get_status` | ตรวจสอบสถานะ | - |

---

## 5. Usage Examples

### 5.1 Basic Memory

```
User: จำไว้ว่าผมชอบกินส้มตำ
Claude: [calls add_memory]

User: ผมชอบกินอะไรนะ?
Claude: [calls search_memory_facts]
```

### 5.2 Procedures

```
User: สอนวิธี deploy โปรเจค
Claude: [calls add_procedure with trigger="deploy", steps=[...]]

User: ช่วย deploy โปรเจคหน่อย
Claude: [calls find_procedures with trigger="deploy"]
```

### 5.3 Identity (Multi-Agent)

```
User: นี่คือการสนทนากับ agent ชื่อ Fon
Claude: [calls set_identity with agent_id="fon"]
```

### 5.4 Oracle Consultation

```
User: ควรใช้ PostgreSQL หรือ MongoDB?
Claude: [calls synapse_consult with query="database choice"]

User: มี pattern อะไรน่าสนใจไหม?
Claude: [calls synapse_reflect or synapse_analyze]
```

---

## 6. Five-Layer Memory

| Layer | Purpose | Decay | Storage |
|-------|---------|-------|---------|
| **1. User Model** | Preferences, expertise | Never | SQLite |
| **2. Procedural** | How-to patterns | ~139 days | SQLite + FTS5 |
| **3. Semantic** | Knowledge, principles | ~69 days | Graphiti |
| **4. Episodic** | Conversation summaries | 90 days TTL | SQLite + FTS5 |
| **5. Working** | Session context | Session only | In-memory |

---

## 7. Docker Compose Reference

### Full Configuration

```yaml
# docker-compose.yml
services:
  falkordb:
    image: falkordb/falkordb:latest
    ports:
      - "6379:6379"
    volumes:
      - falkordb_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    networks:
      - synapse-network

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - synapse-network

  synapse:
    build: .
    ports:
      - "47780:47780"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - FALKORDB_URI=redis://falkordb:6379
    depends_on:
      falkordb:
        condition: service_healthy
    networks:
      - synapse-network

networks:
  synapse-network:

volumes:
  falkordb_data:
  qdrant_data:
```

### Resource Limits

```yaml
synapse:
  deploy:
    resources:
      limits:
        memory: 4G
      reservations:
        memory: 2G
```

---

## 8. Troubleshooting

### 8.1 Container Won't Start

```bash
# Check logs
docker compose logs synapse

# Common issues:
# - Missing ANTHROPIC_API_KEY → Add to .env
# - Port in use → Change SYNAPSE_PORT
# - Out of memory → Increase Docker memory limit
```

### 8.2 Health Check Failing

```bash
# Manual health check
curl http://localhost:47780/health

# Check if FalkorDB is healthy
docker compose logs falkordb

# Restart services
docker compose restart
```

### 8.3 Claude Code Can't Connect

```bash
# Verify server is running
curl http://localhost:47780/mcp

# Check if port is exposed
docker compose ps

# Check firewall (Windows)
netsh advfirewall firewall show rule name="Synapse MCP"
```

### 8.4 Reset Everything

```bash
# Stop and remove all data
docker compose down -v

# Rebuild from scratch
docker compose up -d --build
```

---

## 9. Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│  DOCKER COMMANDS                                            │
├─────────────────────────────────────────────────────────────┤
│  docker compose up -d        → Start all services           │
│  docker compose down         → Stop all services            │
│  docker compose logs -f      → View logs                    │
│  docker compose ps           → Check status                 │
│  docker compose restart      → Restart services             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  CLAUDE CODE CONFIG                                         │
├─────────────────────────────────────────────────────────────┤
│  {                                                          │
│    "mcpServers": {                                          │
│      "synapse": {                                           │
│        "type": "http",                                      │
│        "url": "http://localhost:47780/mcp/"                 │
│      }                                                      │
│    }                                                        │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  KEY TOOLS                                                  │
├─────────────────────────────────────────────────────────────┤
│  add_memory(name, body)      → เพิ่มความจำ                  │
│  search_memory_facts(query)  → ค้นหา facts                 │
│  set_identity(user, agent)   → ตั้งค่า identity            │
│  synapse_consult(query)      → ปรึกษาความจำ               │
│  get_status()                → ตรวจสอบสถานะ               │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. Related Docs

- [README.md](../README.md) - Project overview
- [PROJECT_PLAN.md](./PROJECT_PLAN.md) - Architecture
- [docker-compose.yml](../docker-compose.yml) - Full config

---

*Last updated: 2026-03-17*
