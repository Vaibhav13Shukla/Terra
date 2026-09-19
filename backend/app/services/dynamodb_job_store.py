"""DynamoDB-backed job store (§23) — deployed alternative to
:class:`~app.services.job_store.InMemoryJobStore`, behind the same
:class:`~app.services.job_store.JobStore` interface.

Design choices, deliberately simple (§53 — simplest architecture that
satisfies the requirement):

* The whole :class:`~app.domain.models.AnalysisJob` is stored as one JSON
  string in a single ``data`` attribute, keyed by ``job_id``. This sidesteps
  boto3's well-known Table-resource gotcha where plain Python ``float``
  values are rejected (DynamoDB's native number type wants ``Decimal``) —
  there is no per-field schema to keep in sync with the domain model, and
  round-tripping is exactly ``AnalysisJob.model_validate_json`` /
  ``model_dump_json``, the same as everywhere else in the codebase.
* Every write also sets a ``ttl`` attribute (epoch seconds, 30 days out),
  matching the table's TTL configuration in ``infra/template.yaml`` — bounds
  storage growth automatically (§67).
* ``list_recent`` uses a table scan + client-side sort. Adequate at
  hackathon/demo scale; a production deployment would add a GSI (constant
  partition key, ``created_at`` sort key) instead — noted here rather than
  built, since it cannot be tested without a real DynamoDB table or a fuller
  mocking layer than this environment has (no boto3 installed; see
  docs/adr/003-ai-orchestration.md for the same trade-off applied to Bedrock).

This module is fully unit-testable without `boto3` installed: the
constructor takes a duck-typed ``table`` object (anything with
``put_item``/``get_item``/``scan``, matching the boto3 DynamoDB Table
resource's method names), so tests inject a plain mock. `boto3` is only
imported inside :meth:`DynamoDBJobStore.from_table_name`, used solely for a
real deployment.
"""
from __future__ import annotations

import time
from typing import Any, Protocol

from app.domain.models import AnalysisJob, AnalysisRequest, AnalysisResult, JobStatus
from app.services.job_store import JobNotFoundError, JobStore

_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days, matches infra/template.yaml


class _Table(Protocol):
    """The subset of the boto3 DynamoDB Table resource's API this store
    uses. A `Protocol`, not an import from `boto3`, so this module — and
    anything that only type-checks against it — never requires `boto3` to be
    installed."""

    def put_item(self, Item: dict[str, Any]) -> Any: ...
    def get_item(self, Key: dict[str, Any]) -> dict[str, Any]: ...
    def scan(self, **kwargs: Any) -> dict[str, Any]: ...


class DynamoDBJobStore(JobStore):
    def __init__(self, table: _Table) -> None:
        self._table = table

    @classmethod
    def from_table_name(cls, table_name: str, region: str) -> DynamoDBJobStore:
        """Construct against a real DynamoDB table. Only code path in this
        module that imports `boto3` — used exclusively for a real deployment,
        never by tests."""
        import boto3

        resource = boto3.resource("dynamodb", region_name=region)
        return cls(resource.Table(table_name))

    def _put(self, job: AnalysisJob) -> None:
        self._table.put_item(
            Item={
                "job_id": job.job_id,
                "data": job.model_dump_json(),
                "ttl": int(time.time()) + _TTL_SECONDS,
            }
        )

    def create(self, request: AnalysisRequest) -> AnalysisJob:
        import datetime as _dt
        import uuid

        now = _dt.datetime.now(_dt.UTC)
        job = AnalysisJob(
            job_id=str(uuid.uuid4()),
            status=JobStatus.CREATED,
            request=request,
            created_at=now,
            updated_at=now,
        )
        self._put(job)
        return job

    def get(self, job_id: str) -> AnalysisJob:
        response = self._table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        if item is None:
            raise JobNotFoundError(job_id)
        return AnalysisJob.model_validate_json(item["data"])

    def update_status(self, job_id: str, status: JobStatus) -> AnalysisJob:
        job = self.get(job_id)
        job.touch(status)
        self._put(job)
        return job

    def complete(self, job_id: str, result: AnalysisResult) -> AnalysisJob:
        job = self.get(job_id)
        job.result = result
        job.touch(JobStatus.COMPLETED)
        self._put(job)
        return job

    def fail(self, job_id: str, error: str) -> AnalysisJob:
        job = self.get(job_id)
        job.error = error
        job.touch(JobStatus.FAILED)
        self._put(job)
        return job

    def list_recent(self, limit: int = 20) -> list[AnalysisJob]:
        # Table scan + client-side sort: adequate at hackathon/demo scale,
        # not intended to scale past it — see module docstring.
        items = self._table.scan().get("Items", [])
        jobs = [AnalysisJob.model_validate_json(item["data"]) for item in items]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]
