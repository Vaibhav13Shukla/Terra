"""Job store abstraction (§23, §26).

The API layer creates an :class:`AnalysisJob`, hands it to a worker, and the
frontend polls for status. This module defines the storage interface plus an
in-memory implementation (used locally and in tests, so the default test run
needs no AWS credentials — §61). A DynamoDB-backed implementation can be added
later behind the same interface without touching callers.
"""
from __future__ import annotations

import abc
import datetime as _dt
import uuid

from app.domain.models import AnalysisJob, AnalysisRequest, AnalysisResult, JobStatus


class JobNotFoundError(KeyError):
    """Raised when a job id does not exist in the store."""


class JobStore(abc.ABC):
    """Interface for persisting analysis job state."""

    @abc.abstractmethod
    def create(self, request: AnalysisRequest) -> AnalysisJob:
        """Create a new job in CREATED status and persist it."""

    @abc.abstractmethod
    def get(self, job_id: str) -> AnalysisJob:
        """Fetch a job by id. Raises :class:`JobNotFoundError` if absent."""

    @abc.abstractmethod
    def update_status(self, job_id: str, status: JobStatus) -> AnalysisJob:
        """Advance a job's status (e.g. DISCOVERING -> PROCESSING)."""

    @abc.abstractmethod
    def complete(self, job_id: str, result: AnalysisResult) -> AnalysisJob:
        """Mark a job COMPLETED with its result."""

    @abc.abstractmethod
    def fail(self, job_id: str, error: str) -> AnalysisJob:
        """Mark a job FAILED with an error message."""

    @abc.abstractmethod
    def list_recent(self, limit: int = 20) -> list[AnalysisJob]:
        """List recent jobs, most recent first (§16 — history)."""


class InMemoryJobStore(JobStore):
    """Process-local job store. Not shared across processes/Lambda invocations
    — used for local development, tests, and as the safe default so Terra
    works with zero AWS setup (§61)."""

    def __init__(self) -> None:
        self._jobs: dict[str, AnalysisJob] = {}

    def create(self, request: AnalysisRequest) -> AnalysisJob:
        now = _dt.datetime.now(_dt.UTC)
        job = AnalysisJob(
            job_id=str(uuid.uuid4()),
            status=JobStatus.CREATED,
            request=request,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> AnalysisJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise JobNotFoundError(job_id) from exc

    def update_status(self, job_id: str, status: JobStatus) -> AnalysisJob:
        job = self.get(job_id)
        job.touch(status)
        return job

    def complete(self, job_id: str, result: AnalysisResult) -> AnalysisJob:
        job = self.get(job_id)
        job.result = result
        job.touch(JobStatus.COMPLETED)
        return job

    def fail(self, job_id: str, error: str) -> AnalysisJob:
        job = self.get(job_id)
        job.error = error
        job.touch(JobStatus.FAILED)
        return job

    def list_recent(self, limit: int = 20) -> list[AnalysisJob]:
        # Insertion order (dicts preserve it), reversed — more reliable than
        # sorting by created_at, since two jobs created in rapid succession can
        # land on the same wall-clock tick under low timer resolution.
        jobs = list(self._jobs.values())
        jobs.reverse()
        return jobs[:limit]

    def clear(self) -> None:  # pragma: no cover - test helper
        self._jobs.clear()
