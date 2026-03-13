"""
Thai NLP MCP Tools

Provides Thai language processing tools for the Synapse MCP server.

Tools:
- detect_language: Detect language of text (Thai/English/Mixed)
- preprocess_text: Preprocess text for extraction or search
- tokenize_thai: Tokenize Thai text into words
- normalize_thai: Normalize Thai text (fix typos, remove zero-width)
"""

import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Lazy imports for Thai NLP
_nlp_module = None


def _get_nlp_module():
    """Get NLP module (lazy import)."""
    global _nlp_module
    if _nlp_module is None:
        try:
            from synapse import nlp
            _nlp_module = nlp
        except ImportError as e:
            logger.warning(f"Thai NLP module not available: {e}")
            _nlp_module = False
    return _nlp_module if _nlp_module else None


# Response types
class LanguageDetectionResponse(BaseModel):
    """Response for language detection."""
    language: str
    confidence: float
    thai_ratio: float
    segments: dict[str, list[str]]


class PreprocessResponse(BaseModel):
    """Response for text preprocessing."""
    original: str
    processed: str
    language: str
    thai_ratio: float
    was_normalized: bool
    was_spellchecked: bool


class TokenizeResponse(BaseModel):
    """Response for tokenization."""
    text: str
    tokens: list[str]
    language: str
    token_count: int


class NormalizeResponse(BaseModel):
    """Response for normalization."""
    original: str
    normalized: str
    changes_made: list[str]


def register_thai_nlp_tools(mcp):
    """
    Register Thai NLP tools with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool()
    def detect_language(text: str) -> LanguageDetectionResponse:
        """Detect the language of text (Thai/English/Mixed).

        Useful for determining how to process text before other operations.

        Args:
            text: Input text to analyze

        Returns:
            Language detection result with language code, confidence, and segments
        """
        nlp = _get_nlp_module()
        if nlp is None:
            return LanguageDetectionResponse(
                language="unknown",
                confidence=0.0,
                thai_ratio=0.0,
                segments={},
            )

        try:
            result = nlp.detect_language(text)
            return LanguageDetectionResponse(
                language=result.language,
                confidence=result.confidence,
                thai_ratio=result.thai_ratio,
                segments=result.segments,
            )
        except Exception as e:
            logger.error(f"Error detecting language: {e}")
            return LanguageDetectionResponse(
                language="unknown",
                confidence=0.0,
                thai_ratio=0.0,
                segments={},
            )

    @mcp.tool()
    def preprocess_for_extraction(
        text: str,
        aggressive: bool = False,
    ) -> PreprocessResponse:
        """Preprocess text for entity extraction.

        Normalizes Thai text, fixes common typos, and optionally spellchecks.
        Use this before adding content to the knowledge graph.

        Args:
            text: Input text to preprocess
            aggressive: Use aggressive normalization (more cleanup)

        Returns:
            Preprocessed text with metadata about what was changed
        """
        nlp = _get_nlp_module()
        if nlp is None:
            return PreprocessResponse(
                original=text,
                processed=text,
                language="unknown",
                thai_ratio=0.0,
                was_normalized=False,
                was_spellchecked=False,
            )

        try:
            result = nlp.preprocess_for_extraction(text, aggressive=aggressive)
            return PreprocessResponse(
                original=result.original,
                processed=result.processed,
                language=result.language,
                thai_ratio=result.thai_ratio,
                was_normalized=result.was_normalized,
                was_spellchecked=result.was_spellchecked,
            )
        except Exception as e:
            logger.error(f"Error preprocessing text: {e}")
            return PreprocessResponse(
                original=text,
                processed=text,
                language="unknown",
                thai_ratio=0.0,
                was_normalized=False,
                was_spellchecked=False,
            )

    @mcp.tool()
    def preprocess_for_search(query: str) -> str:
        """Preprocess a search query for full-text search.

        Tokenizes Thai text and removes stopwords.
        Use this before searching the knowledge graph.

        Args:
            query: Search query to preprocess

        Returns:
            Preprocessed query ready for FTS5 search
        """
        nlp = _get_nlp_module()
        if nlp is None:
            return query

        try:
            return nlp.preprocess_for_search(query)
        except Exception as e:
            logger.error(f"Error preprocessing search query: {e}")
            return query

    @mcp.tool()
    def tokenize_thai(text: str) -> TokenizeResponse:
        """Tokenize Thai text into words.

        Thai doesn't use spaces between words, so tokenization is needed
        for proper text processing.

        Args:
            text: Thai text to tokenize

        Returns:
            List of word tokens
        """
        nlp = _get_nlp_module()
        if nlp is None:
            return TokenizeResponse(
                text=text,
                tokens=[text],
                language="unknown",
                token_count=1,
            )

        try:
            # Detect language first
            detection = nlp.detect_language(text)

            # Tokenize based on language
            if detection.language in ("th", "mixed"):
                tokens = nlp.tokenize(text)
            else:
                # Simple whitespace tokenization for non-Thai
                tokens = text.split()

            return TokenizeResponse(
                text=text,
                tokens=tokens,
                language=detection.language,
                token_count=len(tokens),
            )
        except Exception as e:
            logger.error(f"Error tokenizing text: {e}")
            return TokenizeResponse(
                text=text,
                tokens=[text],
                language="unknown",
                token_count=1,
            )

    @mcp.tool()
    def normalize_thai(text: str, level: str = "medium") -> NormalizeResponse:
        """Normalize Thai text.

        Fixes common Thai typos and normalizes whitespace.
        Levels: light, medium, aggressive

        Args:
            text: Thai text to normalize
            level: Normalization level (light, medium, aggressive)

        Returns:
            Normalized text with list of changes made
        """
        nlp = _get_nlp_module()
        if nlp is None:
            return NormalizeResponse(
                original=text,
                normalized=text,
                changes_made=[],
            )

        try:
            normalized = nlp.normalize(text, level=level)

            # Detect changes
            changes = []
            if normalized != text:
                if len(normalized) != len(text):
                    changes.append("whitespace_normalized")
                if any(c in text for c in ["เเ", "ํา", "่ ้"]):
                    changes.append("typos_fixed")
                if "  " in text and "  " not in normalized:
                    changes.append("multiple_spaces_removed")

            return NormalizeResponse(
                original=text,
                normalized=normalized,
                changes_made=changes,
            )
        except Exception as e:
            logger.error(f"Error normalizing text: {e}")
            return NormalizeResponse(
                original=text,
                normalized=text,
                changes_made=[],
            )

    @mcp.tool()
    def is_thai_text(text: str) -> bool:
        """Check if text contains Thai characters.

        Quick check for Thai content without full analysis.

        Args:
            text: Text to check

        Returns:
            True if text contains Thai characters
        """
        nlp = _get_nlp_module()
        if nlp is None:
            return False

        try:
            return nlp.is_thai(text)
        except Exception as e:
            logger.error(f"Error checking Thai text: {e}")
            return False

    logger.info("Thai NLP MCP tools registered")

    return mcp
