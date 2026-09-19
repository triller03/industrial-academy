"""Security middleware: hardened response headers, HTTPS enforcement and
per-IP sliding-window rate limiting for the auth surface."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import Settings

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline security headers to every response."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "0"  # modern CSP replaces this
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = CSP
        return response


class HttpsEnforceMiddleware(BaseHTTPMiddleware):
    """Redirects to https when require_https is set (honours X-Forwarded-Proto)."""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request, call_next):
        if self.settings.require_https:
            scheme = request.headers.get("x-forwarded-proto", request.url.scheme).lower()
            if scheme != "https":
                return JSONResponse(
                    status_code=426,
                    content={"detail": "HTTPS is required. Access this service over TLS."},
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limit keyed on client IP and route family."""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _limit_for(self, path: str) -> int | None:
        if path.startswith("/api/auth/"):
            return self.settings.rate_limit_auth_per_minute
        if not path.startswith("/api/"):
            return None
        return self.settings.rate_limit_global_per_minute

    @staticmethod
    def _client_ip(request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request, call_next):
        path = request.url.path
        limit = self._limit_for(path)
        if limit is None:
            return await call_next(request)
        key = (self._client_ip(request), "auth" if path.startswith("/api/auth/") else "global")
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            while window and now - window[0] > 60.0:
                window.popleft()
            if len(window) >= limit:
                limited = True
            else:
                window.append(now)
                limited = False
        if limited:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again shortly."},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)