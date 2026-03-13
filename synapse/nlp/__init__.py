"""
Synapse NLP Module

Provides Thai language processing with graceful fallbacks.

Features:
- Language detection (Thai/English/Mixed)
- Thai tokenization (with pythainlp or fallback)
- Thai text normalization
- Thai spell checking
- Stopword removal
- Text preprocessing for extraction and search

Usage:
    from synapse.nlp import (
        # Language detection
        detect_language,
        LanguageDetector,
        LanguageRouter,

        # Thai NLP
        is_thai,
        tokenize,
        normalize,
        correct,
        remove_stopwords,
        ThaiDetector,
        ThaiTokenizer,
        ThaiNormalizer,
        ThaiSpellChecker,
        ThaiStopwords,

        # Preprocessing
        preprocess_for_extraction,
        preprocess_for_search,
        preprocess_episode,
        tokenize_for_fts,
        TextPreprocessor,
    )

    # Detect language
    result = detect_language("สวัสดี Hello")
    print(result.language)  # "mixed"

    # Process text
    router = LanguageRouter()
    processed = router.process("ผมชอบ Python")
    print(processed.tokens)  # ['ผม', 'ชอบ', 'Python']

    # Preprocess for extraction
    from synapse.nlp import preprocess_for_extraction
    result = preprocess_for_extraction("คอมพิวเตอร์")
    print(result.processed)  # Normalized text
"""

# Language detection and routing
from .router import (
    LanguageDetector,
    LanguageRouter,
    LanguageResult,
    ProcessResult,
    detect_language,
    get_router,
    preprocess as router_preprocess,
)

# Thai NLP
from .thai import (
    ThaiDetector,
    ThaiTokenizer,
    ThaiNormalizer,
    ThaiSpellChecker,
    ThaiStopwords,
    is_thai,
    tokenize,
    normalize,
    correct,
    remove_stopwords,
)

# Preprocessing
from .preprocess import (
    TextPreprocessor,
    ExtractionPreprocessResult,
    preprocess_for_extraction,
    preprocess_for_search,
    preprocess_episode,
    tokenize_for_fts,
    get_preprocessor,
)


__all__ = [
    # Language detection
    "LanguageDetector",
    "LanguageRouter",
    "LanguageResult",
    "ProcessResult",
    "detect_language",
    "get_router",
    "router_preprocess",
    # Thai NLP
    "ThaiDetector",
    "ThaiTokenizer",
    "ThaiNormalizer",
    "ThaiSpellChecker",
    "ThaiStopwords",
    "is_thai",
    "tokenize",
    "normalize",
    "correct",
    "remove_stopwords",
    # Preprocessing
    "TextPreprocessor",
    "ExtractionPreprocessResult",
    "preprocess_for_extraction",
    "preprocess_for_search",
    "preprocess_episode",
    "tokenize_for_fts",
    "get_preprocessor",
]
