"""
Language Router

Automatically detects and routes text to appropriate language processor.
Supports Thai, English, and mixed content.

Usage:
    from synapse.nlp import LanguageRouter

    router = LanguageRouter()
    lang = router.detect("สวัสดีครับ Hello")
    # → ("th", 0.6)

    processed = router.process("ผมชอบ Python")
    # → {"language": "th", "tokens": [...], "normalized": "..."}
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from functools import lru_cache

from .thai import (
    ThaiDetector,
    ThaiTokenizer,
    ThaiNormalizer,
    ThaiSpellChecker,
    ThaiStopwords,
    is_thai,
    tokenize as thai_tokenize,
    normalize as thai_normalize,
)


@dataclass
class LanguageResult:
    """Result of language detection."""

    language: str  # "th", "en", "mixed", "unknown"
    confidence: float  # 0.0 to 1.0
    thai_ratio: float  # Ratio of Thai chars
    segments: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ProcessResult:
    """Result of text processing."""

    original: str
    language: str
    normalized: str
    tokens: List[str]
    no_stopwords: List[str]
    is_thai: bool


class LanguageDetector:
    """
    Detect language of text content.

    Primary focus on Thai vs English detection.
    """

    # Unicode ranges
    THAI_RANGE = (0x0E00, 0x0E7F)
    ASCII_RANGE = (0x0020, 0x007F)

    # Regex patterns
    THAI_PATTERN = re.compile(r"[\u0E00-\u0E7F]+")
    ASCII_PATTERN = re.compile(r"[a-zA-Z]+")

    @classmethod
    def detect(cls, text: str) -> LanguageResult:
        """
        Detect language of text.

        Args:
            text: Input text

        Returns:
            LanguageResult with detection info
        """
        if not text:
            return LanguageResult(
                language="unknown",
                confidence=0.0,
                thai_ratio=0.0,
            )

        # Count characters by type
        thai_chars = len(cls.THAI_PATTERN.findall(text))
        ascii_chars = len(cls.ASCII_PATTERN.findall(text))
        total_chars = len(text.replace(" ", ""))

        if total_chars == 0:
            return LanguageResult(
                language="unknown",
                confidence=0.0,
                thai_ratio=0.0,
            )

        thai_ratio = thai_chars / total_chars
        ascii_ratio = ascii_chars / total_chars

        # Determine language
        if thai_ratio > 0.7:
            language = "th"
            confidence = thai_ratio
        elif thai_ratio > 0.3:
            language = "mixed"
            confidence = 0.5 + abs(thai_ratio - 0.5)
        elif ascii_ratio > 0.5:
            language = "en"
            confidence = ascii_ratio
        else:
            language = "unknown"
            confidence = 0.0

        # Extract segments
        thai_segments = cls.THAI_PATTERN.findall(text)
        ascii_segments = cls.ASCII_PATTERN.findall(text)

        return LanguageResult(
            language=language,
            confidence=confidence,
            thai_ratio=thai_ratio,
            segments={
                "th": thai_segments,
                "en": ascii_segments,
            },
        )

    @classmethod
    @lru_cache(maxsize=1000)
    def get_language(cls, text: str) -> str:
        """
        Quick language detection (cached).

        Args:
            text: Input text

        Returns:
            Language code ("th", "en", "mixed")
        """
        return cls.detect(text).language


class LanguageRouter:
    """
    Route text to appropriate language processor.

    Provides unified API for multi-language processing.
    """

    def __init__(
        self,
        thai_tokenizer: str = "newmm",
        normalize_level: str = "medium",
    ):
        """
        Initialize Language Router.

        Args:
            thai_tokenizer: Thai tokenizer engine
            normalize_level: Normalization level
        """
        self.thai_tokenizer = thai_tokenizer
        self.normalize_level = normalize_level

    def detect(self, text: str) -> LanguageResult:
        """
        Detect language of text.

        Args:
            text: Input text

        Returns:
            LanguageResult
        """
        return LanguageDetector.detect(text)

    def process(self, text: str) -> ProcessResult:
        """
        Process text with language-appropriate methods.

        Args:
            text: Input text

        Returns:
            ProcessResult with all processing info
        """
        detection = self.detect(text)
        language = detection.language

        # Normalize based on language
        if language == "th":
            normalized = ThaiNormalizer.normalize(text, self.normalize_level)
            tokens = ThaiTokenizer.tokenize(normalized, engine=self.thai_tokenizer)
        elif language == "en":
            normalized = self._normalize_english(text)
            tokens = self._tokenize_english(normalized)
        else:
            # Mixed or unknown
            normalized = self._normalize_mixed(text)
            tokens = self._tokenize_mixed(normalized)

        # Remove stopwords
        no_stopwords = self._remove_stopwords(tokens, language)

        return ProcessResult(
            original=text,
            language=language,
            normalized=normalized,
            tokens=tokens,
            no_stopwords=no_stopwords,
            is_thai=(language in ("th", "mixed")),
        )

    def preprocess_for_search(self, text: str) -> str:
        """
        Preprocess text for search.

        Args:
            text: Query text

        Returns:
            Preprocessed text ready for FTS5
        """
        detection = self.detect(text)

        if detection.language == "th":
            # Tokenize Thai
            tokens = ThaiTokenizer.tokenize(text, engine=self.thai_tokenizer)
            # Remove stopwords
            tokens = ThaiStopwords.remove_stopwords(tokens)
            # Join with spaces for FTS5
            return " ".join(tokens)
        else:
            # English or mixed - simple normalization
            return self._normalize_english(text).lower()

    def preprocess_for_extraction(self, text: str) -> str:
        """
        Preprocess text for entity extraction.

        Args:
            text: Input text

        Returns:
            Preprocessed text
        """
        detection = self.detect(text)

        if detection.thai_ratio > 0.3:
            # Has Thai content - normalize
            normalized = ThaiNormalizer.normalize(text, "medium")
            # Spell check if mostly Thai
            if detection.language == "th":
                normalized = ThaiSpellChecker.correct(normalized)
            return normalized
        else:
            return text

    def _normalize_english(self, text: str) -> str:
        """Normalize English text."""
        # Simple normalization
        text = " ".join(text.split())
        text = text.lower()
        return text

    def _tokenize_english(self, text: str) -> List[str]:
        """Tokenize English text."""
        # Simple whitespace tokenization
        return text.split()

    def _normalize_mixed(self, text: str) -> str:
        """Normalize mixed Thai-English text."""
        # Normalize Thai parts
        return ThaiNormalizer.normalize(text, self.normalize_level)

    def _tokenize_mixed(self, text: str) -> List[str]:
        """Tokenize mixed Thai-English text."""
        tokens = []
        # Split by language segments
        last_end = 0

        for match in LanguageDetector.THAI_PATTERN.finditer(text):
            # Add non-Thai segment before
            if match.start() > last_end:
                non_thai = text[last_end:match.start()]
                tokens.extend(non_thai.split())

            # Add Thai segment
            thai_text = match.group()
            thai_tokens = ThaiTokenizer.tokenize(thai_text)
            tokens.extend(thai_tokens)

            last_end = match.end()

        # Add remaining non-Thai segment
        if last_end < len(text):
            remaining = text[last_end:]
            tokens.extend(remaining.split())

        return [t for t in tokens if t.strip()]

    def _remove_stopwords(self, tokens: List[str], language: str) -> List[str]:
        """Remove stopwords based on language."""
        if language in ("th", "mixed"):
            # Remove Thai stopwords
            tokens = ThaiStopwords.remove_stopwords(tokens)

        if language in ("en", "mixed"):
            # Remove English stopwords
            tokens = self._remove_english_stopwords(tokens)

        return tokens

    def _remove_english_stopwords(self, tokens: List[str]) -> List[str]:
        """Remove English stopwords."""
        english_stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "i", "you", "he", "she", "it", "we", "they", "me", "him",
            "her", "us", "them", "my", "your", "his", "its", "our",
            "and", "or", "but", "if", "then", "else", "when", "where",
            "what", "which", "who", "whom", "this", "that", "these",
            "in", "on", "at", "to", "for", "with", "by", "from", "of",
        }
        return [t for t in tokens if t.lower() not in english_stopwords]


# Singleton instance
_router: Optional[LanguageRouter] = None


def get_router() -> LanguageRouter:
    """Get singleton LanguageRouter instance."""
    global _router
    if _router is None:
        _router = LanguageRouter()
    return _router


# Convenience functions
def detect_language(text: str) -> LanguageResult:
    """Detect language of text."""
    return LanguageDetector.detect(text)


def preprocess(text: str) -> ProcessResult:
    """Process text with language detection."""
    return get_router().process(text)


def preprocess_for_search(text: str) -> str:
    """Preprocess text for search."""
    return get_router().preprocess_for_search(text)


def preprocess_for_extraction(text: str) -> str:
    """Preprocess text for entity extraction."""
    return get_router().preprocess_for_extraction(text)
