"""Storage Module"""

from synapse.storage.falkordb import FalkorDBClient
from synapse.storage.sqlite import SQLiteClient

__all__ = [
    "FalkorDBClient",
    "SQLiteClient",
]
