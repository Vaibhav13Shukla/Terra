"""Analysis job queue abstraction (§ADR 002 — async processing mode).

Only used when ``Settings.terra_processing_mode == "async"``: the API
enqueues the job and returns immediately; a separate worker Lambda (see
app.worker.handler) dequeues it, runs the same deterministic pipeline, and
resolves the job via the same :class:`~app.services.job_store.JobStore`
interface the synchronous path uses.

Follows the same pattern as :mod:`app.services.dynamodb_job_store`: a
``Protocol`` describing only the boto3 SQS client methods actually used, so
this module — and its tests — never require `boto3` to be installed. `boto3`
is imported lazily, only inside :meth:`SQSAnalysisQueue.from_queue_url`,
used exclusively for a real deployment.
"""
from __future__ import annotations

import abc
import json
from typing import Any, Protocol

from app.domain.models import AnalysisRequest


class AnalysisQueue(abc.ABC):
    """Interface for handing off a created job for asynchronous processing."""

    @abc.abstractmethod
    def enqueue(self, job_id: str, request: AnalysisRequest) -> None:
        """Submit a job for processing by a worker."""


class _SQSClient(Protocol):
    """The subset of the boto3 SQS client this module uses."""

    def send_message(self, QueueUrl: str, MessageBody: str) -> Any: ...


class SQSAnalysisQueue(AnalysisQueue):
    def __init__(self, client: _SQSClient, queue_url: str) -> None:
        self._client = client
        self._queue_url = queue_url

    @classmethod
    def from_queue_url(cls, queue_url: str, region: str) -> SQSAnalysisQueue:
        """Construct against a real SQS queue. Only code path in this module
        that imports `boto3` — used exclusively for a real deployment, never
        by tests."""
        import boto3

        return cls(boto3.client("sqs", region_name=region), queue_url)

    def enqueue(self, job_id: str, request: AnalysisRequest) -> None:
        body = json.dumps({"job_id": job_id, "request": json.loads(request.model_dump_json())})
        self._client.send_message(QueueUrl=self._queue_url, MessageBody=body)
