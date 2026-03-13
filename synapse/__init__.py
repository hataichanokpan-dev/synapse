"""
Synapse - Unified AI Memory System

Knowledge Graph + Five-Layer Memory + Thai NLP
"""

__version__ = "0.1.0"

from synapse.layers.types import MemoryLayer, DecayConfig
from synapse.layers.decay import compute_decay_score

__all__ = [
    "MemoryLayer",
    "DecayConfig",
    "compute_decay_score",
]
