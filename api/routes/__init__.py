"""
Routes package for Synapse API.
"""

from api.routes.identity import router as identity_router
from api.routes.memory import router as memory_router
from api.routes.oracle import router as oracle_router
from api.routes.procedures import router as procedures_router
from api.routes.system import router as system_router
from api.routes.graph import router as graph_router
from api.routes.episodes import router as episodes_router
from api.routes.feed import router as feed_router

__all__ = [
    "identity_router",
    "memory_router",
    "oracle_router",
    "procedures_router",
    "system_router",
    "graph_router",
    "episodes_router",
    "feed_router",
]
