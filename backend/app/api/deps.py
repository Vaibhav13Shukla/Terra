"""API dependency providers: job store and provider-registry bootstrap.

Centralized here so the FastAPI route handlers stay thin, and so tests can
reset state between cases (§44 — never scatter configuration/wiring across
components).
"""
from __future__ import annotations

from app.config.settings import get_settings
from app.providers.base import DataProvider, ProviderRegistry
from app.providers.fixtures import demo_decline_provider
from app.providers.sentinel2 import Sentinel2Provider
from app.services.analysis_queue import AnalysisQueue
from app.services.job_store import InMemoryJobStore, JobStore

_job_store: JobStore | None = None
_analysis_queue: AnalysisQueue | None = None


def get_job_store() -> JobStore:
    """Return the process-wide job store.

    Selected by ``Settings.terra_job_store``: ``"memory"`` (default — zero
    AWS setup required to run Terra locally, §61) or ``"dynamodb"`` (deployed
    — see :class:`~app.services.dynamodb_job_store.DynamoDBJobStore`, which
    only imports `boto3` when actually constructed here, never at module
    import time)."""
    global _job_store
    if _job_store is None:
        settings = get_settings()
        if settings.terra_job_store == "dynamodb":
            from app.services.dynamodb_job_store import DynamoDBJobStore

            if not settings.dynamodb_table:
                raise RuntimeError(
                    "TERRA_JOB_STORE=dynamodb requires DYNAMODB_TABLE to be set"
                )
            _job_store = DynamoDBJobStore.from_table_name(
                settings.dynamodb_table, settings.aws_region
            )
        else:
            _job_store = InMemoryJobStore()
    return _job_store


def get_analysis_queue() -> AnalysisQueue:
    """Return the process-wide analysis queue, used only when
    ``Settings.terra_processing_mode == "async"`` (§ADR 002). Raises
    ``RuntimeError`` if async mode is selected without a queue configured —
    a deployment/config error, not a client error."""
    global _analysis_queue
    if _analysis_queue is None:
        settings = get_settings()
        if not settings.analyses_queue_url:
            raise RuntimeError(
                "TERRA_PROCESSING_MODE=async requires ANALYSES_QUEUE_URL to be set"
            )
        from app.services.analysis_queue import SQSAnalysisQueue

        _analysis_queue = SQSAnalysisQueue.from_queue_url(
            settings.analyses_queue_url, settings.aws_region
        )
    return _analysis_queue


def bootstrap_providers() -> None:
    """Idempotently register the built-in providers. Safe to call on every
    request; a no-op once providers are registered."""
    if not ProviderRegistry.names():
        ProviderRegistry.register(Sentinel2Provider())
        ProviderRegistry.register(demo_decline_provider())


def get_provider(name: str) -> DataProvider:
    bootstrap_providers()
    return ProviderRegistry.get(name)


def reset_state() -> None:  # pragma: no cover - test helper
    """Reset job store and provider registry — used between API tests so
    cases don't leak state into one another."""
    global _job_store, _analysis_queue
    _job_store = InMemoryJobStore()
    _analysis_queue = None
    ProviderRegistry.clear()
