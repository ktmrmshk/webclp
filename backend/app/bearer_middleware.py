"""Bearer token gate for /api when WEBCLIP_API_TOKEN is set."""

import hmac
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp


def _bearer_ok(header_value: str | None, expected: str) -> bool:
    if not header_value or not header_value.startswith("Bearer "):
        return False
    got = header_value[7:].strip()
    if not got:
        return False
    try:
        return hmac.compare_digest(got, expected)
    except TypeError:
        return False


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, token: str | None):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next: Callable):
        if self.token is None:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)
        auth = request.headers.get("authorization")
        if _bearer_ok(auth, self.token):
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
