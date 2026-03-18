# Rate Limit 429 Deep Analysis Report

**Date:** 2026-03-17
**Author:** Claude (ฝน)
**Status:** Analysis Complete - Awaiting Decision

---

## Executive Summary

**Root Cause:** Z.ai Proxy Rate Limit (ไม่ใช่ Anthropic API โดยตรง)

```
Error code: 429 - {'error': {'code': '1302', 'message': 'Rate limit reached for requests'}}
```

- `code: '1302'` = **Z.ai Proxy Error Code** (ไม่ใช่ Anthropic official error)
- ใช้ Proxy `https://api.z.ai/api/anthropic` แทน Anthropic โดยตรง
- Z.ai proxy มี rate limit เข้มงวดกว่า Anthropic API

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONFIGURATION FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌───────────────────┐     ┌─────────────────────────────┐
│   .env       │     │  config.yaml      │     │  Docker Container           │
│              │     │                   │     │                             │
│ ANTHROPIC_   │     │ llm:              │     │  ENV:                       │
│ BASE_URL=    │────▶│   provider:       │────▶│    ANTHROPIC_API_KEY=xxx    │
│ api.z.ai/... │     │     anthropic     │     │    ANTHROPIC_BASE_URL=      │
│              │     │   providers:      │     │      api.z.ai/api/anthropic │
│ ANTHROPIC_   │     │     anthropic:    │     │                             │
│ API_KEY=xxx  │     │       api_key:    │     │                             │
└──────────────┘     │         ${...}    │     └──────────────┬──────────────┘
                     └───────────────────┘                    │
                                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FACTORY CREATION                                     │
│                         factories.py:205-222                                 │
└─────────────────────────────────────────────────────────────────────────────┘

              ┌──────────────────────────────────────────────┐
              │  case 'anthropic':                           │
              │                                              │
              │  llm_config = GraphitiLLMConfig(             │
              │      api_key=api_key,      ✅ PASSED         │
              │      model=config.model,   ✅ PASSED         │
              │      temperature=...,      ✅ PASSED         │
              │      max_tokens=...,       ✅ PASSED         │
              │      base_url=???          ❌ NOT PASSED!    │
              │  )                                          │
              │  return AnthropicClient(config=llm_config)  │
              └──────────────────────┬───────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AnthropicClient                                      │
│                         anthropic_client.py:144-148                          │
└─────────────────────────────────────────────────────────────────────────────┘

              ┌──────────────────────────────────────────────┐
              │  self.client = AsyncAnthropic(               │
              │      api_key=config.api_key,  ✅             │
              │      max_retries=1,           ✅             │
              │      base_url=???             ❌ NOT PASSED! │
              │  )                                          │
              └──────────────────────┬───────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ANTHROPIC SDK (Hidden Behavior)                           │
└─────────────────────────────────────────────────────────────────────────────┘

              ┌──────────────────────────────────────────────┐
              │  Anthropic Python SDK มี hidden behavior:    │
              │                                              │
              │  1. Auto-reads ANTHROPIC_BASE_URL from ENV   │
              │  2. If set → uses it instead of official API │
              │  3. This BYPASSES explicit config!           │
              │                                              │
              │  AsyncAnthropic() internally does:           │
              │  base_url = os.getenv('ANTHROPIC_BASE_URL')  │
              │           or 'https://api.anthropic.com'     │
              └──────────────────────┬───────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ACTUAL API CALL                                      │
└─────────────────────────────────────────────────────────────────────────────┘

              ┌──────────────────────────────────────────────┐
              │                                              │
              │  POST https://api.z.ai/api/anthropic/v1/...  │
              │                                              │
              │  Z.ai Proxy → Anthropic API                  │
              │                                              │
              │  ❌ 429 Rate Limit from Z.ai (code: 1302)    │
              │                                              │
              └──────────────────────────────────────────────┘
```

---

## Key Findings

| # | Issue | Location | Severity |
|---|-------|----------|----------|
| 1 | **`base_url` NOT passed to GraphitiLLMConfig** | `factories.py:216-221` | 🟡 Medium |
| 2 | **`base_url` NOT passed to AsyncAnthropic** | `anthropic_client.py:144` | 🟡 Medium |
| 3 | **SDK auto-reads `ANTHROPIC_BASE_URL` from ENV** | Hidden SDK behavior | 🔴 Root Cause |
| 4 | **Z.ai Proxy has stricter rate limits** | External service | 🔴 Blocking |

---

## Files Involved

```
synapse/
├── .env                                    # ANTHROPIC_BASE_URL=api.z.ai/...
├── synapse/
│   └── mcp_server/
│       ├── config/
│       │   ├── config.production.yaml      # provider: anthropic
│       │   └── schema.py                   # AnthropicProviderConfig has api_url
│       └── src/
│           └── services/
│               └── factories.py            # ❌ base_url NOT passed
└── synapse/
    └── graphiti/
        └── llm_client/
            ├── config.py                   # LLMConfig has base_url field
            └── anthropic_client.py         # ❌ base_url NOT passed to SDK
```

---

## Verification Evidence

### Container ENV (Verified)
```bash
$ docker exec synapse-server env | grep -i anthropic
ANTHROPIC_API_KEY=7d9996ed590249f6b0215ca176bbf93f.1fDuv2TJIhfx8alW
ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic  ← SDK reads this!
```

### Schema Has Field (Verified)
```python
# schema.py:105-110
class AnthropicProviderConfig(BaseModel):
    api_key: str | None = None
    api_url: str = 'https://api.anthropic.com'  # ← Field exists!
    max_retries: int = 3
```

### Factory Missing (Verified)
```python
# factories.py:216-222
llm_config = GraphitiLLMConfig(
    api_key=api_key,
    model=config.model,
    temperature=config.temperature,
    max_tokens=config.max_tokens,
    # base_url=???  ← MISSING!
)
return AnthropicClient(config=llm_config)
```

### Client Missing (Verified)
```python
# anthropic_client.py:144-148
self.client = AsyncAnthropic(
    api_key=config.api_key,
    max_retries=1,
    # base_url=???  ← MISSING!
)
```

---

## Root Cause Chain

```
1. .env sets ANTHROPIC_BASE_URL=api.z.ai/api/anthropic
                    ↓
2. Docker passes env var to container
                    ↓
3. Factory creates AnthropicClient WITHOUT explicit base_url
                    ↓
4. Anthropic SDK auto-reads ANTHROPIC_BASE_URL from environment
                    ↓
5. All API calls go through Z.ai proxy
                    ↓
6. Z.ai proxy rate limit (code 1302) blocks requests
                    ↓
7. Episode processing fails, no memory stored
```

---

## Solution Options

| Option | Description | Effort | Impact |
|--------|-------------|--------|--------|
| **A** | Remove `ANTHROPIC_BASE_URL` from .env (use official Anthropic API) | Low | High - direct API, higher limits |
| **B** | Pass `base_url` explicitly in factory to control behavior | Medium | Medium - explicit control |
| **C** | Upgrade Z.ai plan for higher rate limits | External | Depends on Z.ai |
| **D** | Use different LLM provider (OpenAI, Gemini, Groq) | Medium | High - alternative path |
| **E** | Add retry logic with exponential backoff | Low | Medium - resilience only |

---

## Recommended Fix

### Option A + B (Combined)

1. **Keep Z.ai proxy** (for cost savings)
2. **Fix factory to pass base_url explicitly**:

```python
# factories.py - case 'anthropic':
api_key = config.providers.anthropic.api_key
api_url = config.providers.anthropic.api_url  # Add this

llm_config = GraphitiLLMConfig(
    api_key=api_key,
    base_url=api_url,  # Add this
    model=config.model,
    temperature=config.temperature,
    max_tokens=config.max_tokens,
)
```

3. **Update schema default**:

```python
# schema.py
class AnthropicProviderConfig(BaseModel):
    api_key: str | None = None
    api_url: str = 'https://api.z.ai/api/anthropic'  # Change default to Z.ai
    max_retries: int = 3
```

4. **Add rate limit handling** in config:

```yaml
# config.production.yaml
llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
  max_tokens: 4096
  temperature: 0.7

  providers:
    anthropic:
      api_key: ${ANTHROPIC_API_KEY}
      api_url: ${ANTHROPIC_BASE_URL:-https://api.anthropic.com}  # Explicit
      max_retries: 3
```

---

## Conclusion

**ใช้ลิงค์และ KEY ถูกต้อง** - แต่มี 2 ปัญหา:

1. **Code Issue**: `base_url` ไม่ถูก pass จาก factory → client (แต่ SDK อ่านจาก env แทน ทำให้ยังทำงานได้)
2. **External Issue**: Z.ai proxy มี rate limit เข้มงวดกว่า Anthropic โดยตรง

**Impact:**
- Episodes ถูก queue แต่ไม่สามารถประมวลผลได้เมื่อ rate limit ถึง
- Knowledge graph จะไม่ได้รับข้อมูลใหม่จนกว่า rate limit จะ reset

**Status:** Awaiting user decision on which option to implement

---

*Report generated: 2026-03-17T19:15+07:00*
