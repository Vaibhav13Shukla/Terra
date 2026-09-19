"""Amazon Cognito JWT verification.

Verifies access/ID tokens issued by a Cognito User Pool against that pool's
published JWKS (JSON Web Key Set) — no AWS SDK call, no AWS credentials
needed, just an HTTPS fetch of a public key document (cached in-process).
This keeps auth verification cheap and independent of `boto3` (§61 — the
lazy-import-boto3-only-when-deployed pattern used everywhere else in this
codebase, see app.services.dynamodb_job_store / app.agents.bedrock).

Only ever reached when ``Settings.auth_enabled`` is true; see
app.api.auth_deps for the FastAPI dependency that wires this in, and its
mandatory-offline fallback when auth is disabled (matches the Bedrock
adapter's pattern of "optional AWS integration, never required to run
locally").
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JOSEError

_JWKS_CACHE_TTL_SECONDS = 3600
_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class AuthError(Exception):
    """Raised for any token verification failure. The message is safe to
    return to the caller (no internals/stack traces leaked)."""


def _issuer(region: str, user_pool_id: str) -> str:
    return f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"


def _jwks_url(region: str, user_pool_id: str) -> str:
    return f"{_issuer(region, user_pool_id)}/.well-known/jwks.json"


def _get_jwks(region: str, user_pool_id: str) -> dict[str, Any]:
    """Fetch (and cache for an hour) the user pool's public JWKS. Cognito
    rotates these keys extremely rarely and publishes both old and new keys
    during rotation, so an hour of staleness is safe (§53 — simplest
    approach that satisfies the requirement)."""
    cache_key = f"{region}:{user_pool_id}"
    cached = _jwks_cache.get(cache_key)
    now = time.time()
    if cached is not None and now - cached[0] < _JWKS_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        response = httpx.get(_jwks_url(region, user_pool_id), timeout=5.0)
        response.raise_for_status()
        jwks = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AuthError("could not fetch signing keys for token verification") from exc

    _jwks_cache[cache_key] = (now, jwks)
    return jwks


def _signing_key(jwks: dict[str, Any], kid: str) -> dict[str, Any]:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise AuthError("token signed with an unrecognized key")


def verify_jwt(
    token: str,
    *,
    region: str,
    user_pool_id: str,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Verify a Cognito-issued JWT (ID or access token) and return its claims.

    Raises :class:`AuthError` on any failure: expired, malformed, wrong
    issuer/audience, unknown signing key, or unreachable JWKS endpoint. Never
    lets a raw jose/httpx exception escape — callers turn this into a clean
    401, and the message is written to be shown to the caller.
    """
    try:
        header = jwt.get_unverified_header(token)
    except JOSEError as exc:
        raise AuthError("malformed token") from exc

    kid = header.get("kid")
    if not kid:
        raise AuthError("malformed token: missing key id")

    jwks = _get_jwks(region, user_pool_id)
    key = _signing_key(jwks, kid)

    issuer = _issuer(region, user_pool_id)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},  # Cognito access tokens carry no `aud` claim
        )
    except JOSEError as exc:
        raise AuthError(f"invalid token: {exc}") from exc

    token_use = claims.get("token_use")
    if token_use not in ("id", "access"):
        raise AuthError("unsupported token type")

    if client_id:
        # ID tokens carry the client id in `aud`; access tokens in `client_id`.
        expected_client = claims.get("aud") if token_use == "id" else claims.get("client_id")
        if expected_client != client_id:
            raise AuthError("token was not issued for this application")

    return claims
