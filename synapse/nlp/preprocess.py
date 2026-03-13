"""
Text Preprocessing for Synapse

Preprocesses text for entity extraction and search.
Integrates Thai NLP with graceful fallbacks.

Usage:
    from synapse.nlp import preprocess_for_extraction, preprocess_for_search

    # Before entity extraction
    clean_text = preprocess_for_extraction("ผมชอบ Python programming")

    # Before search
    search_query = preprocess_for_search("ค้นหาเกี่ยวกับ machine learning")
"""

import threading
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

from .router import (
    LanguageRouter,
    LanguageDetector,
    LanguageResult,
    ProcessResult,
    get_router,
    detect_language,
)

# Security: Maximum text length to prevent memory exhaustion
MAX_TEXT_LENGTH = 100_000  # 100KB limit


@dataclass
class ExtractionPreprocessResult:
    """Result of preprocessing text for extraction."""

    original: str
    processed: str
    language: str
    thai_ratio: float
    was_normalized: bool
    was_spellchecked: bool


class TextPreprocessor:
    """
    Preprocess text for various Synapse operations.

    Provides unified preprocessing pipeline for:
    - Entity extraction
    - Search queries
    - Episode content
    """

    def __init__(
        self,
        normalize_thai: bool = True,
        spellcheck_thai: bool = True,
        remove_stopwords_for_search: bool = True,
    ):
        """
        Initialize Text Preprocessor.

        Args:
            normalize_thai: Normalize Thai text (fix typos, whitespace)
            spellcheck_thai: Apply Thai spell checking
            remove_stopwords_for_search: Remove stopwords in search preprocessing
        """
        self.normalize_thai = normalize_thai
        self.spellcheck_thai = spellcheck_thai
        self.remove_stopwords_for_search = remove_stopwords_for_search
        self._router = get_router()

    def preprocess_for_extraction(
        self,
        text: str,
        aggressive: bool = False,
    ) -> ExtractionPreprocessResult:
        """
        Preprocess text before entity extraction.

        Steps:
        1. Detect language
        2. Normalize Thai text (fix typos, remove zero-width)
        3. Optionally spellcheck Thai
        4. Preserve original for context

        Args:
            text: Input text
            aggressive: Use aggressive normalization

        Returns:
            ExtractionPreprocessResult with processed text
        """
        if not text:
            return ExtractionPreprocessResult(
                original=text,
                processed=text,
                language="unknown",
                thai_ratio=0.0,
                was_normalized=False,
                was_spellchecked=False,
            )

        # Security: Truncate very long texts to prevent memory exhaustion
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]

        # Detect language
        detection = self._router.detect(text)
        language = detection.language
        thai_ratio = detection.thai_ratio

        processed = text
        was_normalized = False
        was_spellchecked = False

        # Process Thai content
        if thai_ratio > 0.1:  # Has Thai content
            from .thai import ThaiNormalizer, ThaiSpellChecker

            # Normalize
            if self.normalize_thai:
                level = "aggressive" if aggressive else "medium"
                processed = ThaiNormalizer.normalize(processed, level)
                was_normalized = True

            # Spellcheck if mostly Thai
            if self.spellcheck_thai and language == "th":
                processed = ThaiSpellChecker.correct(processed)
                was_spellchecked = True

        return ExtractionPreprocessResult(
            original=text,
            processed=processed,
            language=language,
            thai_ratio=thai_ratio,
            was_normalized=was_normalized,
            was_spellchecked=was_spellchecked,
        )

    def preprocess_for_search(
        self,
        query: str,
        keep_original_tokens: bool = False,
    ) -> str:
        """
        Preprocess search query.

        Uses LanguageRouter.preprocess_for_search internally.

        Args:
            query: Search query
            keep_original_tokens: Keep original tokens alongside processed

        Returns:
            Preprocessed query string
        """
        if not query:
            return query

        processed = self._router.preprocess_for_search(query)

        if keep_original_tokens:
            # Combine original and processed for better matching
            detection = self._router.detect(query)
            if detection.language == "th":
                # For Thai, add original as-is for exact match
                processed = f"{query} {processed}"

        return processed

    def preprocess_episode(
        self,
        episode_body: str,
        source_description: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Preprocess episode content for Graphiti.

        Args:
            episode_body: Episode content
            source_description: Optional source description

        Returns:
            Tuple of (processed_body, metadata)
        """
        if not episode_body:
            return episode_body, {}

        # Process body
        result = self.preprocess_for_extraction(episode_body)

        metadata = {
            "original_language": result.language,
            "thai_ratio": result.thai_ratio,
            "was_normalized": result.was_normalized,
            "was_spellchecked": result.was_spellchecked,
        }

        # Process source description if provided
        if source_description:
            source_result = self.preprocess_for_extraction(source_description)
            metadata["source_language"] = source_result.language

        return result.processed, metadata

    def tokenize_for_fts(
        self,
        text: str,
    ) -> str:
        """
        Tokenize text for FTS5 full-text search.

        Thai text needs word segmentation for FTS5.

        Args:
            text: Input text

        Returns:
            Space-separated tokens
        """
        if not text:
            return ""

        return self._router.preprocess_for_search(text)


# Singleton instance with thread safety
_preprocessor: Optional[TextPreprocessor] = None
_preprocessor_lock = threading.Lock()


def get_preprocessor() -> TextPreprocessor:
    """Get singleton TextPreprocessor instance (thread-safe)."""
    global _preprocessor
    if _preprocessor is None:
        with _preprocessor_lock:
            if _preprocessor is None:  # Double-check pattern
                _preprocessor = TextPreprocessor()
    return _preprocessor


# Convenience functions
def preprocess_for_extraction(
    text: str,
    aggressive: bool = False,
) -> ExtractionPreprocessResult:
    """
    Preprocess text for entity extraction.

    Args:
        text: Input text
        aggressive: Use aggressive normalization

    Returns:
        ExtractionPreprocessResult
    """
    return get_preprocessor().preprocess_for_extraction(text, aggressive)


def preprocess_for_search(query: str) -> str:
    """
    Preprocess query for search.

    Args:
        query: Search query

    Returns:
        Preprocessed query
    """
    return get_preprocessor().preprocess_for_search(query)


def preprocess_episode(
    episode_body: str,
    source_description: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Preprocess episode for Graphiti.

    Args:
        episode_body: Episode content
        source_description: Optional source description

    Returns:
        Tuple of (processed_body, metadata)
    """
    return get_preprocessor().preprocess_episode(episode_body, source_description)


def tokenize_for_fts(text: str) -> str:
    """
    Tokenize text for FTS5.

    Args:
        text: Input text

    Returns:
        Space-separated tokens
    """
    return get_preprocessor().tokenize_for_fts(text)
