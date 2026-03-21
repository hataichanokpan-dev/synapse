"""
UTF-8 JSON Response class for proper Thai/Unicode handling.

Ensures all API responses include charset=utf-8 in Content-Type header.
"""

from starlette.responses import JSONResponse as StarletteJSONResponse


class UTF8JSONResponse(StarletteJSONResponse):
    """JSON response with explicit UTF-8 charset."""
    media_type = "application/json; charset=utf-8"
