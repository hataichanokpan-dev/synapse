"""
LayerClassifier - LLM-based content classification for memory layers

Classifies content into one of five memory layers:
- user_model: User preferences, identity, expertise level
- procedural: Step-by-step instructions, how-to guides, workflows
- semantic: Facts, concepts, principles, definitions
- episodic: Past events, conversations, experiences
- working: Temporary context, current task focus

Uses LLM when available, falls back to keyword matching.
"""

import logging
import os
from typing import Optional, Tuple

from synapse.layers.types import MemoryLayer

logger = logging.getLogger(__name__)


CLASSIFIER_PROMPT = """Classify this content into exactly ONE memory layer. Respond with ONLY the layer name, nothing else.

Layers:
- user_model: User preferences, identity, expertise level, personal information
- procedural: Step-by-step instructions, how-to guides, workflows, commands, recipes
- semantic: Facts, concepts, principles, definitions, knowledge about the world
- episodic: Past events, conversations, experiences, things that happened
- working: Temporary context, current task focus, session-only information

Examples:
- "I prefer Python over JavaScript" -> user_model
- "How to bake a cake: 1. Mix flour..." -> procedural
- "Python is a programming language" -> semantic
- "Yesterday I went to the mall" -> episodic
- "Current task: fix the login bug" -> working

Content: {content}

Layer:"""


class LayerClassifier:
    """
    Classifies content into memory layers using LLM with keyword fallback.

    Supports:
    - Anthropic Claude API
    - OpenAI API
    - Keyword-based fallback
    - Thai content classification
    """

    def __init__(
        self,
        llm_client: Optional[object] = None,
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
            context: Optional context (e.g., temporary=True -> working)

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
            "my preference is", "i like", "ฉันชอบที่จะ",
        ]
        if any(kw in content_lower for kw in user_keywords):
            return MemoryLayer.USER_MODEL, 0.6

        # Layer 2: Procedural keywords (more specific)
        proc_keywords = [
            "วิธีทำ", "ขั้นตอนที่", "how to:", "steps:",
            "step 1", "ขั้นตอนแรก", "first step",
            "procedure:", "algorithm:", "workflow:",
            "tutorial:", "guide:", "คู่มือ", "วิธีการ",
        ]
        if any(kw in content_lower for kw in proc_keywords):
            return MemoryLayer.PROCEDURAL, 0.6

        # Layer 4: Episodic keywords
        epi_keywords = [
            "เมื่อวาน", "วันนี้", "yesterday", "today",
            "เกิดขึ้น", "happened", "บทสนทนา",
            "เรื่องราว", "story", "ประสบการณ์",
            "last week", "last month", "สัปดาห์ที่แล้ว",
            "เมื่อก่อน", "ในอดีต", "ในวัน",
        ]
        if any(kw in content_lower for kw in epi_keywords):
            return MemoryLayer.EPISODIC, 0.6

        # Layer 5: Working (temporary) keywords
        work_keywords = [
            "ชั่วคราว", "ตอนนี้", "temp", "now",
            "current", "session", "กำลังทำ",
            "currently", "right now", "ขณะนี้",
        ]
        if any(kw in content_lower for kw in work_keywords):
            return MemoryLayer.WORKING, 0.5

        # Default: Semantic (facts, concepts)
        return MemoryLayer.SEMANTIC, 0.5
