"""Unit tests for structured logging (§38)."""
from __future__ import annotations

import json

import pytest

from app.observability.logging import log_event, timed_event


def test_log_event_emits_json_line(caplog):
    caplog.set_level("INFO", logger="terra")
    log_event("test_event", job_id="abc123", scenes_used=3)
    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert payload["event"] == "test_event"
    assert payload["job_id"] == "abc123"
    assert payload["scenes_used"] == 3


def test_timed_event_logs_duration_and_ok_status(caplog):
    caplog.set_level("INFO", logger="terra")
    with timed_event("test_op", job_id="j1"):
        pass
    payload = json.loads(caplog.records[0].message)
    assert payload["event"] == "test_op"
    assert payload["status"] == "ok"
    assert "duration_ms" in payload
    assert payload["job_id"] == "j1"


def test_timed_event_logs_error_and_reraises(caplog):
    caplog.set_level("INFO", logger="terra")
    with pytest.raises(ValueError, match="boom"):
        with timed_event("test_op_fail", job_id="j2"):
            raise ValueError("boom")
    payload = json.loads(caplog.records[0].message)
    assert payload["status"] == "error"
    assert payload["error"] == "boom"


def test_log_event_never_crashes_on_non_serializable_via_default_str(caplog):
    caplog.set_level("INFO", logger="terra")

    class Weird:
        def __str__(self):
            return "weird-repr"

    log_event("test_weird", thing=Weird())
    payload = json.loads(caplog.records[0].message)
    assert payload["thing"] == "weird-repr"
