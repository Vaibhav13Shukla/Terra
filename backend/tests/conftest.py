"""Suite-wide guard: the default test run must never touch a real AWS account
(CLAUDE.md golden rule 4 — "works offline, needs no AWS credentials").

Without this, whether the suite stayed offline depended on whether boto3 happened
to be installed. On a machine that has boto3 and a ~/.aws profile (every AWS
developer's laptop, or a CI job that pulls boto3 in as a transitive dependency)
tests that exercised the Bedrock adapter sent real, signed InvokeModel requests
under the developer's default profile. Two layers, so one failing is not enough:

1. Hide every credential source, so no real identity can be resolved.
2. Make botocore refuse to send any HTTP request at all.

botocore's Stubber (used for DynamoDB tests) intercepts before the HTTP layer, so
it is unaffected.
"""
from __future__ import annotations

import pytest

# Paths that do not exist: botocore treats a missing config/credentials file as empty.
_MISSING_CREDENTIALS_FILE = "/nonexistent/terra-tests/aws-credentials"
_MISSING_CONFIG_FILE = "/nonexistent/terra-tests/aws-config"


@pytest.fixture(autouse=True)
def _no_real_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", _MISSING_CREDENTIALS_FILE)
    monkeypatch.setenv("AWS_CONFIG_FILE", _MISSING_CONFIG_FILE)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    try:
        from botocore.httpsession import URLLib3Session
    except ImportError:  # boto3 not installed: nothing can reach AWS anyway
        return

    def _refuse(self, request):  # noqa: ARG001
        raise RuntimeError(
            f"test attempted a real AWS HTTP request to {request.url} — "
            "tests must stub or monkeypatch AWS access"
        )

    monkeypatch.setattr(URLLib3Session, "send", _refuse)
