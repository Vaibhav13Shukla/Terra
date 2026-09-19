"""FastAPI auth dependency.

Mirrors the Bedrock/DynamoDB pattern used across this codebase: a feature
that requires real AWS setup (here, a deployed Cognito User Pool) is fully
optional and defaults OFF, so the app and test suite run with zero AWS setup
(§61, CLAUDE.md golden rule 4 — "works offline"). When
``Settings.auth_enabled`` is false (the default), every request is treated as
an authenticated anonymous caller — this is what local dev and the offline
test suite exercise. Only a real deployment that sets ``AUTH_ENABLED=true``
plus the Cognito settings actually enforces tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request

from app.auth.cognito import AuthError, verify_jwt
from app.config.settings import Settings, get_settings


@dataclass
class AuthenticatedUser:
    """The caller identity attached to a request. ``subject`` is the Cognito
    `sub` claim (stable user id) when auth is enabled, or a fixed anonymous
    id when it's disabled."""

    subject: str
    claims: dict[str, Any] = field(default_factory=dict)


_ANONYMOUS_USER = AuthenticatedUser(subject="anonymous")


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return header.split(" ", 1)[1].strip()


def require_auth(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    """FastAPI dependency: resolve the caller's identity.

    Disabled (default): returns a fixed anonymous identity, no header
    required — this is the path every offline test and local run takes.
    Enabled: requires a valid ``Authorization: Bearer <token>`` header
    verified against the configured Cognito User Pool; raises 401 otherwise.
    """
    if not settings.auth_enabled:
        return _ANONYMOUS_USER

    if not settings.cognito_user_pool_id:
        # Misconfiguration, not a client error: auth is turned on but the
        # pool isn't configured. Fail loudly rather than silently letting
        # everyone through.
        raise HTTPException(status_code=500, detail="authentication is misconfigured")

    token = _extract_bearer_token(request)
    try:
        claims = verify_jwt(
            token,
            region=settings.cognito_region or settings.aws_region,
            user_pool_id=settings.cognito_user_pool_id,
            client_id=settings.cognito_app_client_id,
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=401, detail=str(exc), headers={"WWW-Authenticate": "Bearer"}
        ) from exc

    subject = claims.get("sub")
    if not subject:
        raise HTTPException(status_code=401, detail="token missing subject claim")
    return AuthenticatedUser(subject=subject, claims=claims)


CurrentUser = Annotated[AuthenticatedUser, Depends(require_auth)]
