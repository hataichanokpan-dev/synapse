"""
Synapse REST API Gateway - Main Application

FastAPI application that provides REST endpoints for the Synapse memory system.

Usage:
    cd synapse && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Environment:
    SYNAPSE_API_KEY: API key for authentication (optional)
    CORS_ORIGINS: Comma-separated list of allowed origins
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.deps import init_services, shutdown_services
from api.middleware import ErrorHandlerMiddleware
from api.routes import (
    identity_router,
    memory_router,
    oracle_router,
    procedures_router,
    system_router,
    graph_router,
    episodes_router,
    feed_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    await init_services()
    yield
    # Shutdown
    await shutdown_services()
    print(f"{settings.app_name} shut down")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## Synapse REST API Gateway

REST API for the Synapse Five-Layer Memory System.

### Architecture
```
Browser → FastAPI (:8000) → SynapseService → FalkorDB / Qdrant / SQLite
```

### Authentication
API key via `X-API-Key` header (optional in dev mode).

### Endpoints by Category
- **Memory** (7): CRUD + search + consolidate
- **Procedures** (6): Layer 2 procedural memory
- **Identity** (5): User context + preferences
- **Oracle** (3): Consult, reflect, analyze
- **System** (4): Status, stats, maintenance

### Reference
See `docs/plans/backend_api_plan.md` for full specification.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handler middleware
app.add_middleware(ErrorHandlerMiddleware)

# Include routers
app.include_router(identity_router, prefix="/api/identity", tags=["Identity"])
app.include_router(memory_router, prefix="/api/memory", tags=["Memory"])
app.include_router(oracle_router, prefix="/api/oracle", tags=["Oracle"])
app.include_router(procedures_router, prefix="/api/procedures", tags=["Procedures"])
app.include_router(system_router, prefix="/api/system", tags=["System"])
app.include_router(graph_router, prefix="/api/graph", tags=["Graph"])
app.include_router(episodes_router, prefix="/api/episodes", tags=["Episodes"])
app.include_router(feed_router, prefix="/api/feed", tags=["Feed"])


# Health check (exempt from auth)
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for load balancers and Docker."""
    return {
        "status": "healthy",
        "service": "synapse-api",
        "version": settings.app_version,
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root - redirect to docs."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
