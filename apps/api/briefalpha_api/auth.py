"""Admin token verification.

The admin token is a single shared secret stored at
`data/.secrets/admin_token` (mode 0600, gitignored). Routes that mutate
state or expose unredacted portfolio data MUST depend on
`require_admin_token` so an `Authorization: Bearer <token>` header is
required.

In tests we honour `BRIEFALPHA_SKIP_SECRETS_CHECK=1` and accept the
sentinel header `Bearer test-admin` without touching the filesystem.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import Header, HTTPException, status

from briefalpha_api.settings import SECRETS_DIR

_TEST_TOKEN = "test-admin"


@lru_cache(maxsize=1)
def _load_admin_token() -> str | None:
    if os.environ.get("BRIEFALPHA_SKIP_SECRETS_CHECK") == "1":
        return _TEST_TOKEN
    path: Path = SECRETS_DIR / "admin_token"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip() or None


def reset_admin_token_cache() -> None:
    _load_admin_token.cache_clear()


async def require_admin_token(
    authorization: str | None = Header(default=None),
) -> str:
    """FastAPI dependency: returns the verified token string.

    Raises 401 if the header is missing/malformed and 403 if it does not
    match the on-disk admin_token. The error body always uses the project's
    standard `{error: {code, message}}` envelope.
    """
    expected = _load_admin_token()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "admin_token_unset",
                    "message": "admin_token is not provisioned. Run scripts/init_secrets.sh.",
                }
            },
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "missing_admin_token",
                    "message": "Authorization: Bearer <admin_token> header required.",
                }
            },
        )
    presented = authorization.split(" ", 1)[1].strip()
    if presented != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "invalid_admin_token",
                    "message": "Token does not match.",
                }
            },
        )
    return presented
