"""Terra API — FastAPI application (§43).

    GET  /health
    GET  /v1/providers
    GET  /v1/scenes
    POST /v1/analyses
    GET  /v1/analyses
    GET  /v1/analyses/{job_id}
    GET  /v1/analyses/{job_id}/evidence

Deployed behind API Gateway via Mangum (see `handler` at the bottom) or run
locally with uvicorn (see README "Local development").

Trade-off (documented, §53): analyses run synchronously within the request —
windowed COG reads for a small AOI complete in single-digit seconds (verified
in the feasibility spike), so a true async worker queue is not required for
the hackathon MVP. The job store/status model already matches an async
design, so moving processing to a separate worker Lambda later needs no API
contract change — see docs/adr/002-processing-runtime.md.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.agents.intent_parser import parse_intent
from app.api.deps import bootstrap_providers, get_analysis_queue, get_job_store, get_provider
from app.api.schemas import CreateAnalysisRequest
from app.auth.dependencies import CurrentUser
from app.config.settings import Settings, get_settings
from app.domain.models import (
    AOI,
    AnalysisJob,
    AnalysisRequest,
    AnalysisType,
    DateRange,
    Evidence,
)
from app.observability.logging import log_event, timed_event
from app.providers.base import ProviderRegistry
from app.services.analysis_engine import AnalysisError, run_analysis
from app.services.explain_service import explain
from app.services.geometry import InvalidGeometryError, validate_aoi
from app.services.job_store import JobNotFoundError
from app.services.quality_filter import filter_scenes


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    bootstrap_providers()
    yield


app = FastAPI(
    title="Terra API",
    version="0.1.0",
    description="Earth Observation, without the plumbing.",
    lifespan=_lifespan,
)


def _cors_origins(settings: Settings) -> list[str]:
    raw = settings.cors_allow_origins.strip()
    if raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# CORS_ALLOW_ORIGINS defaults to "*" for local dev; a real deployment sets it
# to the deployed frontend's exact origin(s) (§31, infra/template.yaml).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(get_settings()),
    allow_methods=["GET", "POST"],
    allow_headers=["*", "Authorization"],
)


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # HTTPS is terminated at API Gateway/CloudFront in every real deployment,
    # so this is safe to always send, including in local http:// dev (the
    # header is simply inert there).
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(_SECURITY_HEADERS)
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/providers")
def list_providers() -> dict:
    bootstrap_providers()
    return {"providers": ProviderRegistry.names()}


@app.get("/v1/scenes")
def list_scenes(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    start_date: dt.date,
    end_date: dt.date,
    cloud_threshold: float = 20.0,
    provider: str = "sentinel-2-l2a",
) -> dict:
    """Preview candidate satellite observations for a bbox/date range without
    running a full analysis (§43, §9 — "show satellite observations"). A
    lightweight bbox is used here (rather than the full AOI polygon
    POST /v1/analyses accepts) since this is a browse/discovery endpoint, not
    the pixel-level analysis itself."""
    aoi = AOI(
        coordinates=[
            [
                (min_lon, min_lat),
                (max_lon, min_lat),
                (max_lon, max_lat),
                (min_lon, max_lat),
                (min_lon, min_lat),
            ]
        ]
    )
    try:
        validate_aoi(aoi)
    except InvalidGeometryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        data_provider = get_provider(provider)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    date_range = DateRange(start=start_date, end=end_date)
    candidates = data_provider.search(aoi, date_range, cloud_threshold=cloud_threshold)
    outcome = filter_scenes(candidates, aoi, cloud_threshold)
    return {
        "selected": outcome.selected,
        "rejected": outcome.rejected,
        "scenes_used": outcome.scenes_used,
        "scenes_rejected": outcome.scenes_rejected,
    }


@app.get("/v1/analyses")
def list_analyses(user: CurrentUser, limit: int = 20) -> list[AnalysisJob]:
    return get_job_store().list_recent(limit=limit)


@app.post("/v1/analyses", response_model=AnalysisJob)
def create_analysis(payload: CreateAnalysisRequest, user: CurrentUser) -> AnalysisJob:
    settings = get_settings()

    analysis_type = payload.analysis
    cloud_threshold = payload.cloud_threshold

    if payload.question:
        intent = parse_intent(payload.question, default_cloud_threshold=cloud_threshold)
        if not intent.supported:
            raise HTTPException(status_code=422, detail=intent.reason)
        analysis_type = intent.analysis_type
        cloud_threshold = intent.cloud_threshold

    date_range = DateRange(start=payload.start_date, end=payload.end_date)
    comparison_range = None
    if analysis_type == AnalysisType.NDVI_CHANGE:
        if payload.comparison_start_date and payload.comparison_end_date:
            comparison_range = DateRange(
                start=payload.comparison_start_date, end=payload.comparison_end_date
            )
        else:
            # Default: an equal-length immediately-preceding period (§7.2).
            span = payload.end_date - payload.start_date
            comp_end = payload.start_date - dt.timedelta(days=1)
            comp_start = comp_end - span
            comparison_range = DateRange(start=comp_start, end=comp_end)

    try:
        request = AnalysisRequest(
            aoi=payload.aoi,
            analysis_type=analysis_type,
            date_range=date_range,
            comparison_range=comparison_range,
            cloud_threshold=cloud_threshold,
            provider=payload.provider,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        provider = get_provider(payload.provider)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_store = get_job_store()
    job = job_store.create(request)

    if settings.terra_processing_mode == "async":
        # Enqueue and return immediately; a separate worker Lambda (see
        # app.worker.handler) runs the same pipeline and resolves the job to
        # COMPLETED/FAILED. The job/status model is identical either way, so
        # a poller (GET /v1/analyses/{id}) can't tell which mode produced it
        # (§ADR 002 — moving to async needs no API contract change).
        try:
            get_analysis_queue().enqueue(job.job_id, request)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return job

    try:
        with timed_event(
            "analysis_completed",
            job_id=job.job_id,
            analysis_type=analysis_type,
            provider=payload.provider,
        ):
            result = run_analysis(provider, request)
    except AnalysisError as exc:
        # Invalid input (bad AOI): the request itself was wrong.
        job_store.fail(job.job_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Anything else (STAC outage after exhausting retries, a provider
        # bug, ...) must still resolve the job to FAILED — otherwise it's
        # stranded in CREATED forever and GET /v1/analyses/{id} can never
        # report a status the polling contract can interpret (§26, §60).
        # timed_event already logged this with status="error" before
        # re-raising; this only decides the job/HTTP outcome.
        job_store.fail(job.job_id, str(exc))
        raise HTTPException(
            status_code=502, detail=f"analysis could not be completed: {exc}"
        ) from exc

    log_event(
        "analysis_result",
        job_id=job.job_id,
        status=result.status,
        scenes_used=result.data_quality.scenes_used if result.data_quality else None,
        scenes_rejected=result.data_quality.scenes_rejected if result.data_quality else None,
    )

    result.explanation = explain(result, settings)
    return job_store.complete(job.job_id, result)


@app.get("/v1/analyses/{job_id}", response_model=AnalysisJob)
def get_analysis(job_id: str, user: CurrentUser) -> AnalysisJob:
    try:
        return get_job_store().get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"analysis '{job_id}' not found") from exc


@app.get("/v1/analyses/{job_id}/evidence", response_model=Evidence)
def get_evidence(job_id: str, user: CurrentUser) -> Evidence:
    try:
        job = get_job_store().get(job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"analysis '{job_id}' not found") from exc
    if job.result is None or job.result.evidence is None:
        raise HTTPException(status_code=404, detail="no evidence available for this analysis")
    return job.result.evidence


# AWS Lambda entry point (API Gateway -> Lambda via Mangum). `mangum` is only
# needed when actually deployed; guarded so local dev/tests never require it.
try:  # pragma: no cover - exercised only in a Lambda deployment
    from mangum import Mangum

    handler = Mangum(app)
except ImportError:  # pragma: no cover
    handler = None
