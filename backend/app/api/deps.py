"""API dependency providers: job store and provider-registry bootstrap.

Centralized here so the FastAPI route handlers stay thin, and so tests can
reset state between cases (§44 — never scatter configuration/wiring across
components).
"""
from __future__ import annotations

from app.providers.base import DataProvider, ProviderRegistry
from app.providers.fixtures import demo_decline_provider
from app.providers.sentinel2 import Sentinel2Provider
from app.services.job_store import InMemoryJobStore, JobStore

_job_store: JobStore = InMemoryJobStore()


def get_job_store() -> JobStore:
    """Return the process-wide job store.

    Always in-memory today (§61 — zero AWS setup required to run Terra
    locally). A DynamoDB-backed store can be swapped in here behind the same
    :class:`~app.services.job_store.JobStore` interface once deployed."""
    return _job_store


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
    global _job_store
    _job_store = InMemoryJobStore()
    ProviderRegistry.clear()
