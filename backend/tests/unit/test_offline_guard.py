"""The suite-wide guard in tests/conftest.py must actually hold when boto3 IS
installed. These use obviously fake credentials, so they are safe even if the guard
were broken — but a broken guard would make them fail, which is the point."""
from __future__ import annotations

import pytest

boto3 = pytest.importorskip("boto3")


def test_no_real_aws_credentials_can_be_resolved():
    assert boto3.Session().get_credentials() is None


def test_botocore_refuses_to_send_a_request(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "fake-test-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-test-secret")
    client = boto3.client("bedrock-runtime", region_name="us-west-2")

    with pytest.raises(RuntimeError, match="real AWS HTTP request"):
        client.invoke_model(modelId="fake-model", body=b"{}")
