"""
Authentication middleware for Synapse API.

Simple API key authentication for single-user system.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.config import settings
from api.responses import UTF8JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """
    API Key authentication middleware.

    Validates X-API-Key header on all requests except:
    - /health (health check)
    - /docs (Swagger UI)
    - /redoc (ReDoc)
    - /openapi.json
    """

    EXEMPT_PATHS = {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
    EXEMPT_PREFIXES = ("/docs", "/redoc")

    async def dispatch(self, request: Request, call_next):
        # Check if path is exempt
        path = request.url.path
        if path in self.EXEMPT_PATHS or any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return await call_next(request)

        # Check API key
        api_key = request.headers.get(settings.api_key_header) or request.query_params.get("api_key")

        if not api_key:
            return UTF8JSONResponse(
                status_code=401,
                content={
                    "error": "Missing API key",
                    "detail": f"Provide {settings.api_key_header} header or api_key query parameter",
                    "code": "AUTH_MISSING",
                },
            )

        if api_key != settings.api_key:
            return UTF8JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid API key",
                    "detail": "The provided API key is not valid",
                    "code": "AUTH_INVALID",
                },
            )

        return await call_next(request)
