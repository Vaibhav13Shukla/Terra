"""Structured logging (§38).

Emits JSON log lines to stdout via the standard library `logging` module.
No third-party dependency: AWS Lambda/CloudWatch captures stdout directly, so
this works identically locally (readable JSON lines in the terminal) and
deployed (searchable/filterable CloudWatch Logs) with zero extra setup.

Never logs credentials, tokens, or other secrets — only operational fields
(job id, analysis type, scene counts, durations, status).
"""
from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from typing import Any

_logger = logging.getLogger("terra")
if not _logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def log_event(event: str, **fields: Any) -> None:
    """Emit one structured JSON log line.

    Example::

        log_event("analysis_completed", job_id=job.job_id, analysis="ndvi_change",
                   scenes_used=3, duration_ms=8420, status="success")
    """
    payload = {"event": event, **fields}
    _logger.info(json.dumps(payload, default=str))


@contextmanager
def timed_event(event: str, **fields: Any):
    """Context manager that logs ``event`` on exit with an added
    ``duration_ms`` field, and ``status="error"`` plus ``error`` if the block
    raised (the exception is re-raised unchanged — this only observes)."""
    t0 = time.perf_counter()
    try:
        yield
    except Exception as exc:
        log_event(
            event,
            duration_ms=round((time.perf_counter() - t0) * 1000, 1),
            status="error",
            error=str(exc),
            **fields,
        )
        raise
    else:
        log_event(
            event,
            duration_ms=round((time.perf_counter() - t0) * 1000, 1),
            status="ok",
            **fields,
        )
