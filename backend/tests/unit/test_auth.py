"""Unit tests for Cognito JWT verification (app.auth.cognito).

Fully offline: generates an RSA keypair in-process, builds a JWKS document
from its public key, signs test tokens with the private key, and monkeypatches
the JWKS fetch so no network call is made — matching this codebase's rule
that the default test run needs no network and no AWS credentials (§61).
"""

from __future__ import annotations

import time

import pytest
from jose import jwt

from app.auth import cognito

REGION = "us-west-2"
POOL_ID = "us-west-2_TestPool"
CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL_ID}"
KID = "test-key-1"


@pytest.fixture
def rsa_keypair():
    from cryptography.hazmat.primitives.asymmetric import rsa

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk_from_public_key(private_key, kid: str) -> dict:
    public_numbers = private_key.public_key().public_numbers()

    def _b64(n: int) -> str:
        import base64

        length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64(public_numbers.n),
        "e": _b64(public_numbers.e),
    }


def _sign(private_key, claims: dict, kid: str = KID) -> str:
    from cryptography.hazmat.primitives import serialization

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


def _base_claims(**overrides) -> dict:
    now = int(time.time())
    claims = {
        "sub": "user-123",
        "token_use": "access",
        "client_id": CLIENT_ID,
        "iss": ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return claims


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch, rsa_keypair):
    jwks = {"keys": [_jwk_from_public_key(rsa_keypair, KID)]}
    monkeypatch.setattr(cognito, "_get_jwks", lambda region, pool_id: jwks)
    yield


def test_verify_jwt_accepts_valid_access_token(rsa_keypair):
    token = _sign(rsa_keypair, _base_claims())
    claims = cognito.verify_jwt(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)
    assert claims["sub"] == "user-123"


def test_verify_jwt_accepts_valid_id_token(rsa_keypair):
    token = _sign(rsa_keypair, _base_claims(token_use="id", aud=CLIENT_ID, client_id=None))
    claims = cognito.verify_jwt(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)
    assert claims["sub"] == "user-123"


def test_verify_jwt_rejects_expired_token(rsa_keypair):
    now = int(time.time())
    token = _sign(rsa_keypair, _base_claims(iat=now - 7200, exp=now - 3600))
    with pytest.raises(cognito.AuthError):
        cognito.verify_jwt(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)


def test_verify_jwt_rejects_wrong_issuer(rsa_keypair):
    token = _sign(rsa_keypair, _base_claims(iss="https://evil.example.com/pool"))
    with pytest.raises(cognito.AuthError):
        cognito.verify_jwt(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)


def test_verify_jwt_rejects_wrong_client_id(rsa_keypair):
    token = _sign(rsa_keypair, _base_claims(client_id="some-other-client"))
    with pytest.raises(cognito.AuthError):
        cognito.verify_jwt(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)


def test_verify_jwt_rejects_unsupported_token_use(rsa_keypair):
    token = _sign(rsa_keypair, _base_claims(token_use="refresh"))
    with pytest.raises(cognito.AuthError):
        cognito.verify_jwt(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)


def test_verify_jwt_rejects_unknown_signing_key(rsa_keypair):
    token = _sign(rsa_keypair, _base_claims(), kid="unknown-kid")
    with pytest.raises(cognito.AuthError):
        cognito.verify_jwt(token, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)


def test_verify_jwt_rejects_malformed_token():
    with pytest.raises(cognito.AuthError):
        cognito.verify_jwt("not-a-jwt", region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)


def test_verify_jwt_rejects_tampered_signature(rsa_keypair):
    token = _sign(rsa_keypair, _base_claims())
    tampered = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    with pytest.raises(cognito.AuthError):
        cognito.verify_jwt(tampered, region=REGION, user_pool_id=POOL_ID, client_id=CLIENT_ID)
