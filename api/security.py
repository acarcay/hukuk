"""
API-key authentication for sensitive endpoints.

Behaviour
---------
* If ``settings.API_KEY`` is set, every protected endpoint requires an
  ``X-API-Key`` request header whose value matches it.  A constant-time
  comparison is used to avoid timing attacks.
* If ``settings.API_KEY`` is empty (the default), authentication is
  DISABLED and the dependency is a no-op.  This keeps local development
  and the test suite friction-free.  A warning is logged once at startup
  (see ``api.main``) so this can't be shipped to production unnoticed.

Usage::

    from fastapi import Depends
    from api.security import require_api_key

    @router.post("/upload", dependencies=[Depends(require_api_key)])
    async def upload(...):
        ...
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from api.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency that enforces the ``X-API-Key`` header when enabled."""
    if not settings.auth_enabled:
        return  # auth disabled (local/dev) — allow through

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide it via the 'X-API-Key' header.",
            headers={"WWW-Authenticate": "API-Key"},
        )
