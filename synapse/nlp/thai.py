"""
Thai NLP Client

Provides Thai language processing using pythainlp with graceful fallbacks.

Features:
- Thai text detection
- Word tokenization
- Text normalization
- Spell checking
- Stopword removal
- Transliteration
"""

import re
from typing import List, Optional, Tuple, Set
from functools import lru_cache

# Lazy imports for pythainlp
_thainlp_available = None


def _check_thainlp() -> bool:
    """Check if pythainlp is available."""
    global _thainlp_available
    if _thainlp_available is None:
        try:
            import pythainlp
            _thainlp_available = True
        except ImportError:
            _thainlp_available = False
    return _thainlp_available


class ThaiDetector:
    """
    Detect Thai text in mixed content.

    Methods:
        is_thai(text) → bool: Check if text contains Thai
        thai_ratio(text) → float: Ratio of Thai characters
        extract_thai(text) → List[str]: Extract Thai segments
    """

    # Thai Unicode range
    THAI_RANGE = (0x0E00, 0x0E7F)

    # Thai characters regex
    THAI_PATTERN = re.compile(r"[\u0E00-\u0E7F]+")

    @classmethod
    def is_thai(cls, text: str) -> bool:
        """
        Check if text contains Thai characters.

        Args:
            text: Input text

        Returns:
            True if contains Thai
        """
        return bool(cls.THAI_PATTERN.search(text))

    @classmethod
    def thai_ratio(cls, text: str) -> float:
        """
        Calculate ratio of Thai characters in text.

        Args:
            text: Input text

        Returns:
            Ratio 0.0 to 1.0
        """
        if not text:
            return 0.0

        thai_chars = len(cls.THAI_PATTERN.findall(text))
        total_chars = len(text.replace(" ", ""))

        if total_chars == 0:
            return 0.0

        return thai_chars / total_chars

    @classmethod
    def extract_thai(cls, text: str) -> List[str]:
        """
        Extract Thai text segments from mixed content.

        Args:
            text: Mixed text

        Returns:
            List of Thai segments
        """
        return cls.THAI_PATTERN.findall(text)

    @classmethod
    def detect_language(cls, text: str) -> Tuple[str, float]:
        """
        Detect primary language of text.

        Args:
            text: Input text

        Returns:
            (language, confidence) tuple
        """
        if not text:
            return ("unknown", 0.0)

        thai_ratio = cls.thai_ratio(text)

        if thai_ratio > 0.5:
            return ("th", thai_ratio)
        elif thai_ratio > 0.1:
            return ("mixed", thai_ratio)
        else:
            return ("en", 1.0 - thai_ratio)


class ThaiNormalizer:
    """
    Normalize Thai text.

    Handles:
    - Remove repeated characters (ดดด → ด)
    - Normalize vowels (เเ → แ)
    - Remove zero-width characters
    - Normalize whitespace
    """

    # Patterns for normalization
    REPEATED_CHARS = re.compile(r"(.)\1{2,}")
    ZERO_WIDTH = re.compile(r"[\u200B-\u200D\uFEFF]")

    # Common Thai typos
    TYPOS = {
        "เเ": "แ",  # Common typo
        "ํา": "ำ",  # Normalization
        "่ ้": "้่",  # Tone mark order
    }

    @classmethod
    def normalize(cls, text: str, level: str = "medium") -> str:
        """
        Normalize Thai text.

        Args:
            text: Input text
            level: Normalization level (light, medium, aggressive)

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Remove zero-width characters
        text = cls.ZERO_WIDTH.sub("", text)

        # Fix common typos
        for wrong, right in cls.TYPOS.items():
            text = text.replace(wrong, right)

        if level in ("medium", "aggressive"):
            # Normalize whitespace
            text = " ".join(text.split())

        if level == "aggressive":
            # Remove excessive repetition
            text = cls.REPEATED_CHARS.sub(r"\1\1", text)

        return text.strip()

    @classmethod
    def remove_diacritics(cls, text: str) -> str:
        """
        Remove Thai tone marks and diacritics.

        Useful for search matching.

        Args:
            text: Thai text

        Returns:
            Text without diacritics
        """
        # Thai diacritics (tone marks, etc.)
        diacritics = "่้๊๋" + "ัิีืุู" + "็" + "ํ" + "ฺ"
        return "".join(c for c in text if c not in diacritics)


class ThaiTokenizer:
    """
    Thai word tokenizer.

    Uses pythainlp if available, falls back to simple rules.
    """

    @classmethod
    def tokenize(
        cls,
        text: str,
        engine: str = "newmm",
        keep_whitespace: bool = False,
    ) -> List[str]:
        """
        Tokenize Thai text into words.

        Args:
            text: Thai text
            engine: Tokenizer engine (newmm, attacut, longest)
            keep_whitespace: Keep whitespace tokens

        Returns:
            List of tokens
        """
        if not text:
            return []

        if _check_thainlp():
            try:
                from pythainlp.tokenize import word_tokenize
                tokens = word_tokenize(
                    text,
                    engine=engine,
                    keep_whitespace=keep_whitespace,
                )
                return tokens
            except Exception:
                pass

        # Fallback: simple regex-based tokenization
        return cls._simple_tokenize(text, keep_whitespace)

    @classmethod
    def _simple_tokenize(cls, text: str, keep_whitespace: bool) -> List[str]:
        """
        Simple tokenization without pythainlp.

        Uses regex to split on word boundaries.
        """
        # Split on spaces first
        parts = text.split()

        tokens = []
        for part in parts:
            # Split Thai from non-Thai
            segments = re.split(r"([\u0E00-\u0E7F]+)", part)
            for seg in segments:
                if seg:
                    if ThaiDetector.is_thai(seg):
                        # For Thai, use character-based fallback
                        # This is not ideal but better than nothing
                        tokens.append(seg)
                    else:
                        tokens.append(seg)

            if keep_whitespace and parts.index(part) < len(parts) - 1:
                tokens.append(" ")

        return tokens

    @classmethod
    def sent_tokenize(cls, text: str) -> List[str]:
        """
        Split Thai text into sentences.

        Args:
            text: Thai text

        Returns:
            List of sentences
        """
        if not text:
            return []

        if _check_thainlp():
            try:
                from pythainlp.tokenize import sent_tokenize as th_sent_tokenize
                return th_sent_tokenize(text)
            except Exception:
                pass

        # Fallback: split on Thai sentence endings
        # Thai sentence ends: . ! ? ฯ
        pattern = r"(?<=[.!?ฯ])\s+"
        return [s.strip() for s in re.split(pattern, text) if s.strip()]


class ThaiSpellChecker:
    """
    Thai spell checker using pythainlp.
    """

    @classmethod
    def spellcheck(cls, text: str) -> List[Tuple[str, bool, List[str]]]:
        """
        Check spelling and get suggestions.

        Args:
            text: Thai text

        Returns:
            List of (word, is_correct, suggestions)
        """
        if not text:
            return []

        tokens = ThaiTokenizer.tokenize(text, keep_whitespace=False)
        results = []

        if _check_thainlp():
            try:
                from pythainlp.spell import spell_check
                from pythainlp.spell import correct as th_correct

                for token in tokens:
                    if not ThaiDetector.is_thai(token):
                        # Skip non-Thai tokens
                        results.append((token, True, []))
                        continue

                    corrected = th_correct(token)
                    is_correct = (corrected == token)

                    if is_correct:
                        results.append((token, True, []))
                    else:
                        # Get suggestions
                        suggestions = spell_check(token)
                        results.append((token, False, suggestions[:5]))

                return results
            except Exception:
                pass

        # Fallback: no spell checking
        return [(token, True, []) for token in tokens]

    @classmethod
    def correct(cls, text: str) -> str:
        """
        Auto-correct Thai text.

        Args:
            text: Thai text with possible errors

        Returns:
            Corrected text
        """
        if not text:
            return ""

        tokens = ThaiTokenizer.tokenize(text, keep_whitespace=False)

        if _check_thainlp():
            try:
                from pythainlp.spell import correct as th_correct

                corrected = []
                for token in tokens:
                    if ThaiDetector.is_thai(token):
                        corrected.append(th_correct(token))
                    else:
                        corrected.append(token)

                return " ".join(corrected)
            except Exception:
                pass

        # Fallback: return original
        return text


class ThaiStopwords:
    """
    Thai stopword handling.
    """

    _stopwords: Optional[Set[str]] = None

    @classmethod
    def get_stopwords(cls) -> Set[str]:
        """
        Get Thai stopwords set.

        Returns:
            Set of stopwords
        """
        if cls._stopwords is None:
            if _check_thainlp():
                try:
                    from pythainlp.corpus import thai_stopwords
                    cls._stopwords = thai_stopwords()
                    return cls._stopwords
                except Exception:
                    pass

            # Fallback: basic stopwords
            cls._stopwords = cls._get_basic_stopwords()

        return cls._stopwords

    @classmethod
    def _get_basic_stopwords(cls) -> Set[str]:
        """Get basic Thai stopwords without pythainlp."""
        return {
            # Common particles
            "ครับ", "ค่ะ", "นะ", "คะ", "จ้ะ", "จ้า", "นะครับ", "นะคะ",
            # Pronouns
            "ฉัน", "ผม", "เขา", "เธอ", "มัน", "เรา", "พวกเขา",
            # Common verbs
            "เป็น", "มี", "ทำ", "ไป", "มา", "ได้", "ให้", "กับ",
            # Common adverbs
            "ก็", "จะ", "ไว้", "แล้ว", "จึง", "เพราะ", "ถ้า",
            # Question words
            "อะไร", "ที่ไหน", "เมื่อไหร่", "ทำไม", "อย่างไร",
            # Others
            "นี้", "นั้น", "โน้น", "ที่", "ซึ่ง", "อัน", "แต่", "หรือ", "และ",
        }

    @classmethod
    def remove_stopwords(cls, tokens: List[str]) -> List[str]:
        """
        Remove stopwords from token list.

        Args:
            tokens: List of tokens

        Returns:
            Tokens without stopwords
        """
        stopwords = cls.get_stopwords()
        return [t for t in tokens if t not in stopwords and t.strip()]


# Convenience functions
def is_thai(text: str) -> bool:
    """Check if text contains Thai."""
    return ThaiDetector.is_thai(text)


def tokenize(text: str, **kwargs) -> List[str]:
    """Tokenize Thai text."""
    return ThaiTokenizer.tokenize(text, **kwargs)


def normalize(text: str, level: str = "medium") -> str:
    """Normalize Thai text."""
    return ThaiNormalizer.normalize(text, level)


def correct(text: str) -> str:
    """Auto-correct Thai text."""
    return ThaiSpellChecker.correct(text)


def remove_stopwords(tokens: List[str]) -> List[str]:
    """Remove Thai stopwords."""
    return ThaiStopwords.remove_stopwords(tokens)
