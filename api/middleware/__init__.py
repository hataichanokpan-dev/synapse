"""
Middleware package for Synapse API.
"""

from api.middleware.auth import AuthMiddleware
from api.middleware.error_handler import ErrorHandlerMiddleware

__all__ = ["AuthMiddleware", "ErrorHandlerMiddleware"]
