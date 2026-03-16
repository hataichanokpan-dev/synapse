# Phase 2: High Priority Fixes (P1)

> **Duration**: 2-3 days
> **Goal**: Improve accuracy and usability
> **Assignee**: เดฟ (Dev) 🦀
> **Reviewer**: Mneme 🧠
> **Dependencies**: Phase 1 (P0) Complete

---

## Overview

Phase 2 เน้นปรับปรุง core functionality ให้ทำงานได้แม่นยำขึ้น โดยเฉพาะ:
- Layer classification ที่แม่นยำขึ้น
- Default configuration ที่เหมาะสม
- Multi-user support
- Bug fixes เล็กน้อย

---

## Tasks

### Task 2.1: LLM-Based Layer Detection

| Field | Value |
|-------|-------|
| **Priority** | P1 - High |
| **Est. Time** | 4 hours |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | Phase 1 (need LLM client from SynapseService) |

#### Problem

`detect_layer()` ใช้ naive keyword matching — ไม่แม่นยำ โดยเฉพาะภาษาไทย

**Evidence** (Lines 174-208):
```python
# manager.py - Naive keyword matching
proc_keywords = ["วิธี", "ขั้นตอน", "how to", "steps", "procedure", "ทำอย่างไร"]
if any(kw in content_lower for kw in proc_keywords):
    return MemoryLayer.PROCEDURAL
```

**Problem Example**:
- "วิธีที่ฉันรู้สึกวันนี้" → จะถูกจัดเป็น Procedural (ผิด!)
- ควรเป็น Episodic (เป็นเรื่องความรู้สึก ไม่ใช่วิธีทำ)

#### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `synapse/classifiers/__init__.py` | CREATE | Package init |
| `synapse/classifiers/layer_classifier.py` | CREATE | LLM-based classifier |
| `synapse/layers/manager.py` | MODIFY | Use new classifier |

#### Implementation Details

**Step 1: Create `synapse/classifiers/__init__.py`**

```python
"""Synapse Classifiers - Content classification modules"""

from .layer_classifier import LayerClassifier

__all__ = ["LayerClassifier"]
```

**Step 2: Create `synapse/classifiers/layer_classifier.py`**

```python
"""
LayerClassifier - LLM-based content classification for memory layers
"""

import logging
import os
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class MemoryLayer(Enum):
    USER_MODEL = "user_model"
    PROCEDURAL = "procedural"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    WORKING = "working"


CLASSIFIER_PROMPT = """Classify this content into exactly ONE memory layer. Respond with ONLY the layer name, nothing else.

Layers:
- user_model: User preferences, identity, expertise level, personal information
- procedural: Step-by-step instructions, how-to guides, workflows, commands, recipes
- semantic: Facts, concepts, principles, definitions, knowledge about the world
- episodic: Past events, conversations, experiences, things that happened
- working: Temporary context, current task focus, session-only information

Examples:
- "I prefer Python over JavaScript" → user_model
- "How to bake a cake: 1. Mix flour..." → procedural
- "Python is a programming language" → semantic
- "Yesterday I went to the mall" → episodic
- "Current task: fix the login bug" → working

Content: {content}

Layer:"""


class LayerClassifier:
    """
    Classifies content into memory layers using LLM with keyword fallback.
    """

    def __init__(
        self,
        llm_client: Optional[any] = None,
        use_llm: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize classifier.

        Args:
            llm_client: LLM client (Anthropic, OpenAI, etc.)
            use_llm: Whether to use LLM classification (default: True)
            confidence_threshold: Minimum confidence for LLM result
        """
        self.llm_client = llm_client
        self.use_llm = use_llm and (llm_client is not None)
        self.confidence_threshold = confidence_threshold

        # Feature flag for easy enable/disable
        self._llm_enabled = os.getenv("SYNAPSE_USE_LLM_CLASSIFICATION", "true").lower() == "true"

    async def classify(
        self,
        content: str,
        context: Optional[dict] = None,
    ) -> Tuple[MemoryLayer, float]:
        """
        Classify content into a memory layer.

        Args:
            content: Content to classify
            context: Optional context (e.g., temporary=True → working)

        Returns:
            Tuple of (layer, confidence)
        """
        # Check context hints first
        if context:
            if context.get("temporary"):
                return MemoryLayer.WORKING, 1.0
            if context.get("user_preference"):
                return MemoryLayer.USER_MODEL, 1.0

        # Try LLM classification if enabled
        if self.use_llm and self._llm_enabled and self.llm_client:
            try:
                layer, confidence = await self._classify_with_llm(content)
                if confidence >= self.confidence_threshold:
                    return layer, confidence
                logger.debug(f"LLM confidence {confidence} below threshold, using fallback")
            except Exception as e:
                logger.warning(f"LLM classification failed: {e}, using keyword fallback")

        # Fallback to keyword matching
        return self._classify_with_keywords(content)

    async def _classify_with_llm(self, content: str) -> Tuple[MemoryLayer, float]:
        """Use LLM to classify content."""

        prompt = CLASSIFIER_PROMPT.format(content=content[:1000])  # Truncate long content

        # Call LLM (support multiple providers)
        response = await self._call_llm(prompt)

        # Parse response
        layer_name = response.strip().lower().replace("-", "_")

        # Map to MemoryLayer
        layer_map = {
            "user_model": MemoryLayer.USER_MODEL,
            "user model": MemoryLayer.USER_MODEL,
            "procedural": MemoryLayer.PROCEDURAL,
            "semantic": MemoryLayer.SEMANTIC,
            "episodic": MemoryLayer.EPISODIC,
            "working": MemoryLayer.WORKING,
        }

        layer = layer_map.get(layer_name, MemoryLayer.SEMANTIC)

        # LLM responses are generally high confidence
        return layer, 0.9

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM provider."""

        # Anthropic client
        if hasattr(self.llm_client, 'messages'):
            response = await self.llm_client.messages.create(
                model="claude-haiku-4-5-20251001",  # Fast, cheap model
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

        # OpenAI client
        if hasattr(self.llm_client, 'chat'):
            response = await self.llm_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast, cheap model
                max_tokens=50,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content

        raise ValueError("Unsupported LLM client")

    def _classify_with_keywords(self, content: str) -> Tuple[MemoryLayer, float]:
        """Fallback keyword-based classification."""

        content_lower = content.lower()

        # Layer 1: User Model keywords
        user_keywords = [
            "ฉันชอบ", "ผู้ใช้ชอบ", "my preference", "i prefer",
            "ฉันเป็นผู้เชี่ยวชาญ", "i am expert", "my expertise",
            "ฉันต้องการ", "i want", "ฉันจะ", "i will",
        ]
        if any(kw in content_lower for kw in user_keywords):
            return MemoryLayer.USER_MODEL, 0.6

        # Layer 2: Procedural keywords (more specific)
        proc_keywords = [
            "วิธีทำ", "ขั้นตอนที่", "how to:", "steps:",
            "step 1", "ขั้นตอนแรก", "first step",
            "procedure:", "algorithm:", "workflow:",
        ]
        if any(kw in content_lower for kw in proc_keywords):
            return MemoryLayer.PROCEDURAL, 0.6

        # Layer 4: Episodic keywords
        epi_keywords = [
            "เมื่อวาน", "วันนี้", "yesterday", "today",
            "เกิดขึ้น", "happened", "บทสนทนา",
            "เรื่องราว", "story", "ประสบการณ์",
        ]
        if any(kw in content_lower for kw in epi_keywords):
            return MemoryLayer.EPISODIC, 0.6

        # Layer 5: Working (temporary) keywords
        work_keywords = [
            "ชั่วคราว", "ตอนนี้", "temp", "now",
            "current", "session", "กำลังทำ",
        ]
        if any(kw in content_lower for kw in work_keywords):
            return MemoryLayer.WORKING, 0.5

        # Default: Semantic (facts, concepts)
        return MemoryLayer.SEMANTIC, 0.5
```

**Step 3: Modify `synapse/layers/manager.py`**

```python
# Add import
from synapse.classifiers import LayerClassifier

# In LayerManager.__init__
self.classifier = LayerClassifier(
    llm_client=llm_client,  # From SynapseService
    use_llm=True,
)

# Modify detect_layer method
async def detect_layer(
    self,
    content: str,
    context: Optional[Dict[str, Any]] = None,
) -> MemoryLayer:
    """Detect appropriate layer for content using LLM or keyword fallback."""
    layer, confidence = await self.classifier.classify(content, context)
    logger.debug(f"Detected layer: {layer.value} (confidence: {confidence})")
    return layer
```

#### Acceptance Criteria

- [ ] LayerClassifier class created
- [ ] LLM classification works with Anthropic/OpenAI
- [ ] Keyword fallback works when LLM unavailable
- [ ] Feature flag `SYNAPSE_USE_LLM_CLASSIFICATION` works
- [ ] Thai content classified correctly
- [ ] Confidence threshold applied

#### Test Cases

```python
import pytest

@pytest.mark.asyncio
async def test_classify_user_preference():
    classifier = LayerClassifier(llm_client=None, use_llm=False)
    layer, conf = await classifier.classify("ฉันชอบภาษา Python")
    assert layer == MemoryLayer.USER_MODEL

@pytest.mark.asyncio
async def test_classify_procedural():
    classifier = LayerClassifier(llm_client=None, use_llm=False)
    layer, conf = await classifier.classify("วิธีทำข้าวผัด: 1. ตั้งกระทะ")
    assert layer == MemoryLayer.PROCEDURAL

@pytest.mark.asyncio
async def test_classify_episodic():
    classifier = LayerClassifier(llm_client=None, use_llm=False)
    layer, conf = await classifier.classify("เมื่อวานฉันไปตลาด")
    assert layer == MemoryLayer.EPISODIC

@pytest.mark.asyncio
async def test_llm_classification_with_mock(mock_llm_client):
    classifier = LayerClassifier(llm_client=mock_llm_client, use_llm=True)
    layer, conf = await classifier.classify("วิธีที่ฉันรู้สึกวันนี้")
    # With LLM, this should be EPISODIC, not PROCEDURAL
    assert layer == MemoryLayer.EPISODIC
```

---

### Task 2.2: Default Embedding Model Configuration

| Field | Value |
|-------|-------|
| **Priority** | P1 - High |
| **Est. Time** | 30 minutes |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | None |

#### Problem

QdrantClient fallback ไป `_hash_embedding()` เมื่อไม่มี embedding model — ไม่มี default และไม่มี warning

**Evidence** (Lines 306-324):
```python
def _load_embedder(self) -> Any | None:
    model_name = (self.embedding_model or '').strip()
    if not model_name:
        self._embedder = None
        return None  # ← No default, no warning!
```

#### Files to Modify

| File | Action |
|------|--------|
| `synapse/storage/qdrant_client.py` | MODIFY |

#### Implementation Details

```python
# Add constant at top of file
DEFAULT_EMBEDDING_MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
# Why this model:
# - รองรับภาษาไทยได้ดี (multilingual)
# - ขนาดเล็ก (118MB)
# - ทำงาน offline ได้
# - 384 dimensions

# Modify _load_embedder method
def _load_embedder(self) -> Any | None:
    """Load Sentence Transformers embedding model."""
    if self._embedder_loaded:
        return self._embedder

    self._embedder_loaded = True

    # Use provided model or default
    use_default = not self.embedding_model
    model_name = (self.embedding_model or DEFAULT_EMBEDDING_MODEL).strip()

    # Warn if using default
    if use_default:
        logger.warning(
            f"SYNAPSE_QDRANT_EMBEDDING_MODEL not set. "
            f"Using default: {DEFAULT_EMBEDDING_MODEL}. "
            f"Vector search will work but may not be optimal for your use case. "
            f"Set SYNAPSE_QDRANT_EMBEDDING_MODEL to suppress this warning."
        )

    try:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading embedding model: {model_name}")
        self._embedder = SentenceTransformer(model_name)
        dimension = self._embedder.get_sentence_embedding_dimension()
        if dimension:
            self.vector_size = int(dimension)
            logger.info(f"Embedding dimension: {self.vector_size}")
    except ImportError:
        logger.error(
            "sentence-transformers not installed. "
            "Install with: pip install sentence-transformers"
        )
        self._embedder = None
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        self._embedder = None

    return self._embedder
```

#### Acceptance Criteria

- [ ] Default model is `paraphrase-multilingual-MiniLM-L12-v2`
- [ ] Warning logged when using default
- [ ] Warning logged when model fails to load
- [ ] Hash fallback still works for offline scenarios

#### Test Cases

```python
def test_default_model_used():
    client = QdrantClient(embedding_model=None)
    # Should use default model
    assert client.embedding_model is None
    # After loading, should have embedder
    embedder = client._load_embedder()
    assert embedder is not None

def test_warning_logged(caplog):
    with caplog.at_level(logging.WARNING):
        client = QdrantClient(embedding_model=None)
        client._load_embedder()
    assert "SYNAPSE_QDRANT_EMBEDDING_MODEL not set" in caplog.text

def test_custom_model_overrides_default():
    client = QdrantClient(embedding_model="custom-model")
    embedder = client._load_embedder()
    # Should attempt to load custom model
```

---

### Task 2.3: User Isolation for Multi-User Support

| Field | Value |
|-------|-------|
| **Priority** | P1 - High |
| **Est. Time** | 1 day |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | Phase 1 (SynapseService) |

#### Problem

Singleton pattern ทำให้ multi-user ไม่ได้ — ทุก managers ใช้ global singleton เดียวกัน

**Evidence**:
```python
# manager.py
_manager: Optional[LayerManager] = None

def get_layer_manager() -> LayerManager:
    global _manager
    if _manager is None:
        _manager = LayerManager()
    return _manager
```

#### Files to Modify

| File | Action |
|------|--------|
| `synapse/layers/manager.py` | MODIFY - Main changes |
| `synapse/layers/semantic.py` | MODIFY - Update singleton |
| `synapse/layers/episodic.py` | MODIFY - Update singleton |
| `synapse/layers/procedural.py` | MODIFY - Update singleton |
| `synapse/layers/working.py` | MODIFY - Update singleton |
| `synapse/layers/user_model.py` | MODIFY - Update singleton |

#### Implementation Details

**Step 1: Create `synapse/layers/context.py`**

```python
"""
UserContext - Per-user isolation for memory managers
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.layers.semantic import SemanticManager
    from synapse.layers.episodic import EpisodicManager
    from synapse.layers.procedural import ProceduralManager
    from synapse.layers.working import WorkingMemoryManager
    from synapse.layers.user_model import UserModelManager


@dataclass
class UserContext:
    """
    Holds all manager instances for a specific user.

    Each user gets their own:
    - Database files (SQLite)
    - Manager instances
    - Working memory
    """

    user_id: str
    db_base_path: Path

    # Lazy-loaded managers
    _semantic: Optional["SemanticManager"] = field(default=None, repr=False)
    _episodic: Optional["EpisodicManager"] = field(default=None, repr=False)
    _procedural: Optional["ProceduralManager"] = field(default=None, repr=False)
    _working: Optional["WorkingMemoryManager"] = field(default=None, repr=False)
    _user_model: Optional["UserModelManager"] = field(default=None, repr=False)

    @classmethod
    def create(cls, user_id: str, base_path: Optional[Path] = None) -> "UserContext":
        """Create a new UserContext with proper paths."""
        if base_path is None:
            base_path = Path.home() / ".synapse"

        user_path = base_path / "users" / user_id
        user_path.mkdir(parents=True, exist_ok=True)

        return cls(user_id=user_id, db_base_path=user_path)

    @property
    def semantic(self) -> "SemanticManager":
        if self._semantic is None:
            from synapse.layers.semantic import SemanticManager
            self._semantic = SemanticManager(db_path=self.db_base_path / "semantic.db")
        return self._semantic

    @property
    def episodic(self) -> "EpisodicManager":
        if self._episodic is None:
            from synapse.layers.episodic import EpisodicManager
            self._episodic = EpisodicManager(db_path=self.db_base_path / "episodic.db")
        return self._episodic

    @property
    def procedural(self) -> "ProceduralManager":
        if self._procedural is None:
            from synapse.layers.procedural import ProceduralManager
            self._procedural = ProceduralManager(db_path=self.db_base_path / "procedural.db")
        return self._procedural

    @property
    def working(self) -> "WorkingMemoryManager":
        if self._working is None:
            from synapse.layers.working import WorkingMemoryManager
            self._working = WorkingMemoryManager(db_path=self.db_base_path / "working.db")
        return self._working

    @property
    def user_model(self) -> "UserModelManager":
        if self._user_model is None:
            from synapse.layers.user_model import UserModelManager
            self._user_model = UserModelManager(db_path=self.db_base_path / "user_model.db")
        return self._user_model
```

**Step 2: Modify `synapse/layers/manager.py`**

```python
# Replace singleton with user-aware context manager
from synapse.layers.context import UserContext

_contexts: Dict[str, UserContext] = {}
_default_context: Optional[UserContext] = None


def get_layer_manager(user_id: str = "default") -> "LayerManager":
    """
    Get LayerManager for specific user.

    Args:
        user_id: User identifier (default: "default")

    Returns:
        LayerManager instance for the user
    """
    global _default_context

    if user_id == "default" and _default_context is not None:
        return LayerManager(user_context=_default_context)

    if user_id not in _contexts:
        _contexts[user_id] = UserContext.create(user_id)
        if user_id == "default":
            _default_context = _contexts[user_id]

    return LayerManager(user_context=_contexts[user_id])


def clear_user_context(user_id: str) -> bool:
    """Clear context for a user (for testing/cleanup)."""
    if user_id in _contexts:
        del _contexts[user_id]
        if user_id == "default":
            global _default_context
            _default_context = None
        return True
    return False
```

**Step 3: Update LayerManager to use UserContext**

```python
class LayerManager:
    def __init__(
        self,
        user_context: Optional[UserContext] = None,
        user_id: str = "default",
        db_base_path: Optional[Path] = None,
    ):
        if user_context is None:
            user_context = UserContext.create(user_id, db_base_path)

        self.user_context = user_context
        self.user_id = user_context.user_id

        # Use managers from context
        self._episodic = user_context.episodic
        self._procedural = user_context.procedural
        self._semantic = user_context.semantic
        self._working = user_context.working
        self._user_model = user_context.user_model
```

#### Acceptance Criteria

- [ ] UserContext class created
- [ ] Each user has separate database files
- [ ] get_layer_manager(user_id="alice") != get_layer_manager(user_id="bob")
- [ ] Feature flag `SYNAPSE_USE_USER_ISOLATION` works
- [ ] Backward compatible with existing code (user_id="default")

#### Test Cases

```python
def test_user_isolation():
    # Create managers for different users
    manager_a = get_layer_manager(user_id="alice")
    manager_b = get_layer_manager(user_id="bob")

    # Add data for alice
    manager_a.record_episode("Alice's secret", source="test")

    # Bob should not see Alice's data
    results = manager_b.find_episodes_by_topic("secret")
    assert len(results) == 0

    # Alice should see her data
    results = manager_a.find_episodes_by_topic("secret")
    assert len(results) == 1

def test_separate_db_paths():
    manager_a = get_layer_manager(user_id="alice")
    manager_b = get_layer_manager(user_id="bob")

    assert "alice" in str(manager_a.user_context.db_base_path)
    assert "bob" in str(manager_b.user_context.db_base_path)
```

---

### Task 2.4: Remove Duplicate FTS5 Virtual Table Creation

| Field | Value |
|-------|-------|
| **Priority** | P1 - High |
| **Est. Time** | 15 minutes |
| **Assignee** | เดฟ (Dev) |
| **Reviewer** | Mneme |
| **Dependencies** | None |

#### Problem

`episodic.py` สร้าง `episodes_fts` virtual table 2 ครั้ง schema ต่างกัน

**Evidence** (Lines 119-121, 134-137):
```python
# First creation — CORRECT
conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
    USING fts5(content_fts, summary_fts, content='episodes', content_rowid='rowid')
""")

# Second creation — WRONG, different schema
conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
    USING fts5(summary, content='episodes', content_rowid='rowid')
""")
```

#### Files to Modify

| File | Action |
|------|--------|
| `synapse/layers/episodic.py` | MODIFY - Remove duplicate |

#### Implementation Details

Simply remove the second CREATE statement (lines 134-137 or wherever it appears).

**Before**:
```python
# FTS5 for full-text search (using tokenized content/summary)
conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
    USING fts5(content_fts, summary_fts, content='episodes', content_rowid='rowid')
""")

# ... some code ...

# FTS5 for full-text search on summaries  ← REMOVE THIS BLOCK
conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
    USING fts5(summary, content='episodes', content_rowid='rowid')
""")
```

**After**:
```python
# FTS5 for full-text search (using tokenized content/summary)
conn.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
    USING fts5(content_fts, summary_fts, content='episodes', content_rowid='rowid')
""")

# ... rest of code (duplicate removed) ...
```

#### Acceptance Criteria

- [ ] Only one CREATE VIRTUAL TABLE for episodes_fts
- [ ] Schema uses `content_fts, summary_fts` (tokenized columns)
- [ ] FTS5 search still works

#### Test Cases

```python
def test_fts_search_works():
    manager = EpisodicManager()
    manager.record_episode("ทดสอบการค้นหา", source="test")

    # Search should work
    results = manager.search_episodes("ค้นหา")
    assert len(results) > 0
```

---

## Phase 2 Milestone

### M2: Phase 2 Complete

**Completion Criteria**:
- [ ] LLM-based layer classification working
- [ ] Default embedding model configured with warning
- [ ] User isolation implemented
- [ ] FTS5 duplicate removed
- [ ] All tests passing
- [ ] No P1 bugs remaining

**Verification Commands**:

```bash
# Test LLM classification (if enabled)
curl -X POST http://localhost:47780/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "add_memory",
      "arguments": {
        "name": "test_classify",
        "episode_body": "วิธีที่ฉันรู้สึกวันนี้คือมีความสุข"
      }
    },
    "id": 1
  }'

# Check logs for classification
docker compose logs synapse-server | grep "Detected layer"

# Test user isolation
# (Manual: create two users, verify data separation)
```

---

## Review Checklist (Mneme)

### Code Review

- [ ] LayerClassifier has proper error handling
- [ ] UserContext is thread-safe
- [ ] FTS5 schema is correct
- [ ] No memory leaks in context management

### Integration Review

- [ ] LLM client injection works
- [ ] Feature flags are respected
- [ ] Backward compatibility maintained

### Performance Review

- [ ] LLM classification doesn't block (async)
- [ ] Context caching is efficient
- [ ] No N+1 queries

---

## Rollback Plan

```bash
# Disable LLM classification
export SYNAPSE_USE_LLM_CLASSIFICATION=false

# Disable user isolation (use default context)
export SYNAPSE_USE_USER_ISOLATION=false

# Revert code
git revert HEAD~N
docker compose restart synapse-server
```

---

*Phase 2 Plan created: 2026-03-16*
*Assignee: เดฟ (Dev) 🦀*
*Reviewer: Mneme 🧠*
