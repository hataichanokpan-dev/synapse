"""
Error handling middleware for Synapse API.

Provides consistent error responses and sanitization in production.
"""

import traceback
from typing import Callable

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.config import settings
from api.responses import UTF8JSONResponse


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handler middleware.

    - Catches all unhandled exceptions
    - Returns consistent JSON error responses
    - Sanitizes stack traces in production
    """

    async def dispatch(self, request: Request, call_next: Callable):
        try:
            return await call_next(request)
        except HTTPException as exc:
            # FastAPI HTTPExceptions - pass through with consistent format
            return UTF8JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.detail if isinstance(exc.detail, str) else "Request error",
                    "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                    "code": getattr(exc, "code", "HTTP_ERROR"),
                },
            )
        except Exception as exc:
            # Unexpected errors
            error_msg = str(exc)

            # In production, don't expose internal details
            if not settings.debug:
                detail = "An internal error occurred"
                stack = None
            else:
                detail = error_msg
                stack = traceback.format_exc()

            # Log the error
            print(f"[ERROR] Unhandled error: {error_msg}")
            if settings.debug:
                print(stack)

            return UTF8JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "detail": detail,
                    "code": "INTERNAL_ERROR",
                    "stack": stack,
                },
            )
