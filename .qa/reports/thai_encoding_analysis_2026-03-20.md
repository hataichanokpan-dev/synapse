# Thai Encoding Analysis Report

> Date: 2026-03-20
> Analyst: Orga (QA Agent) + Codex + Fon

## 🔍 Problem

Thai characters stored in Synapse display as `???????` in episodes.

## 📊 Root Cause Analysis

### Layer 1: Windows Console (CONFIRMED)
```
Windows:
  sys.stdout.encoding = cp1252  ❌ (no Thai support)
  sys.stderr.encoding = cp1252  ❌
  locale.getpreferredencoding() = cp1252 ❌

Docker Container:
  sys.stdout.encoding = utf-8   ✅
  sys.stderr.encoding = utf-8   ✅
```

### Layer 2: Database Storage (CONFIRMED)
```
FalkorDB Query Result:
  "QA Principles - Orga" content shows:
  "Mock ???? = ?????? verify ???????"
```

Data is ALREADY corrupted in FalkorDB before retrieval.

### Layer 3: graphiti-core (SUSPECTED)

The corruption happens when graphiti-core serializes data for FalkorDB/Redis.

## 🛠️ Fixes Applied

### 1. main.py - UTF-8 stdio wrapper for Windows ✅
```python
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
```

### 2. docker-compose.yml - Environment variables ✅
```yaml
- PYTHONIOENCODING=utf-8
- LANG=C.UTF-8
```

### 3. mcp_config_stdio_example.json - Environment ✅
```json
"PYTHONIOENCODING": "utf-8",
"LANG": "C.UTF-8"
```

## ⚠️ Remaining Issue

The encoding fix in main.py only affects **local Windows execution**.
For Docker containers, the issue is in **graphiti-core** library serialization.

### Recommended Next Steps

1. **Check graphiti-core encoding** - The library may be using default encoding
2. **Check Redis/FalkorDB client** - Ensure it uses UTF-8 for all string operations
3. **Add encoding tests** - Create unit tests specifically for Thai content

## 📋 Test Results

| Test | Status | Notes |
|------|--------|-------|
| test_add_memory_* | ✅ PASS | Tests pass but don't verify Thai encoding |
| Episode retrieval | ❌ FAIL | Thai shows as `????` |
| FalkorDB query | ❌ FAIL | Data corrupted in DB |

## 🎯 Conclusion

- **Partial fix applied**: Windows stdio encoding
- **Root cause**: graphiti-core or FalkorDB client serialization
- **Priority**: P1 - Needs investigation of graphiti-core library

---

*Report by Orga QA Agent*
