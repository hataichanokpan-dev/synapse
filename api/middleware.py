"""
Middleware for Synapse API.
"""

import traceback
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """API Key authentication middleware."""

    EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/"}
    EXEMPT_PREFIXES = ("/docs", "/redoc")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self.EXEMPT_PATHS or any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return await call_next(request)

        api_key = request.headers.get(settings.api_key_header) or request.query_params.get("api_key")
        if not api_key or api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid API key", "code": "AUTH_INVALID"},
            )
        return await call_next(request)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler middleware."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": str(exc.detail),
                    "code": "HTTP_ERROR",
                },
            )
        except Exception as exc:
            error_msg = str(exc)
            if not settings.debug:
                detail = "Internal server error"
                stack = None
            else:
                detail = error_msg
                stack = traceback.format_exc()

            print(f"❌ Error: {error_msg}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": detail,
                    "stack": stack,
                },
            )
