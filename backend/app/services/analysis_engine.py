"""The analysis engine (§6, §critical-path).

Orchestrates the deterministic pipeline end-to-end:

    AOI/date validation -> provider search -> quality filter -> windowed reads
    -> NDVI -> period comparison -> evidence -> AnalysisResult

This module contains NO AI. It is what §8 calls "deterministic code" — the
engine an LLM-produced :class:`AnalysisRequest` is handed to. It never fabricates
a result: if there is no usable data, it returns a "failed" result with a clear,
human-readable message (§27, §60) rather than guessing.
"""
from __future__ import annotations

import time

import numpy as np

from app.domain.models import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisType,
    DataQuality,
    DateRange,
    Evidence,
    Metric,
    ProcessingStep,
    Scene,
)
from app.processing.ndvi import (
    apply_reflectance,
    compute_ndvi,
    percentage_change,
    scl_valid_mask,
)
from app.providers.base import DataProvider
from app.services.geometry import InvalidGeometryError, validate_aoi
from app.services.quality_filter import filter_scenes

NDVI_FORMULA = "NDVI = (NIR - RED) / (NIR + RED)"


class AnalysisError(Exception):
    """Raised for input errors the caller should surface as a 4xx-style failure
    (as opposed to a "no data found" result, which is a valid, successful
    response describing an unsuccessful analysis)."""


def run_analysis(provider: DataProvider, request: AnalysisRequest) -> AnalysisResult:
    """Execute ``request`` against ``provider`` and return a decision-ready result.

    Raises :class:`AnalysisError` for invalid input (bad geometry). Returns a
    ``status="failed"`` :class:`AnalysisResult` — not an exception — when the
    request is valid but no usable data exists, since that is a legitimate,
    explainable outcome (§27).
    """
    try:
        validate_aoi(request.aoi)
    except InvalidGeometryError as exc:
        raise AnalysisError(str(exc)) from exc

    if request.analysis_type == AnalysisType.NDVI_CHANGE:
        return _run_ndvi_change(provider, request)
    if request.analysis_type == AnalysisType.NDVI_SNAPSHOT:
        return _run_ndvi_snapshot(provider, request)

    # Unreachable while AnalysisType has only two members, but guards against
    # a new enum member being added without matching engine support (§59).
    raise AnalysisError(f"unsupported analysis_type: {request.analysis_type}")


def _period_ndvi_mean(
    provider: DataProvider,
    request: AnalysisRequest,
    date_range: DateRange,
    steps: list[ProcessingStep],
    label: str,
) -> tuple[float | None, list[Scene], list[Scene], float | None]:
    """Compute mean NDVI over one period. Returns
    (mean_ndvi, selected_scenes, rejected_scenes, valid_pixel_ratio)."""
    t0 = time.perf_counter()
    candidates = provider.search(
        request.aoi, date_range, cloud_threshold=request.cloud_threshold
    )
    steps.append(
        ProcessingStep(
            name=f"search:{label}",
            detail=f"found {len(candidates)} candidate scene(s) via provider "
            f"'{provider.name}' for {date_range.start}..{date_range.end}",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
    )

    outcome = filter_scenes(candidates, request.aoi, request.cloud_threshold)
    steps.append(
        ProcessingStep(
            name=f"filter:{label}",
            detail=f"selected {outcome.scenes_used}, rejected {outcome.scenes_rejected} "
            f"(cloud_threshold={request.cloud_threshold}%)",
        )
    )

    if not outcome.selected:
        return None, outcome.selected, outcome.rejected, None

    ndvi_means: list[float] = []
    valid_ratios: list[float] = []
    t0 = time.perf_counter()
    for scene in outcome.selected:
        red_win = provider.read_window(scene, "red", request.aoi)
        nir_win = provider.read_window(scene, "nir", request.aoi)
        red = apply_reflectance(red_win.array, red_win.scale, red_win.offset)
        nir = apply_reflectance(nir_win.array, nir_win.scale, nir_win.offset)

        valid_mask = None
        if "scl" in scene.assets:
            scl_win = provider.read_window(scene, "scl", request.aoi)
            valid_mask = scl_valid_mask(scl_win.array)

        field = compute_ndvi(red, nir, valid_mask=valid_mask)
        if field.stats.valid_pixels > 0:
            ndvi_means.append(field.stats.mean)
            valid_ratios.append(field.stats.valid_ratio)

    steps.append(
        ProcessingStep(
            name=f"ndvi:{label}",
            detail=f"computed NDVI for {len(ndvi_means)}/{len(outcome.selected)} scene(s)",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )
    )

    if not ndvi_means:
        return None, outcome.selected, outcome.rejected, None

    mean_ndvi = float(np.mean(ndvi_means))
    mean_valid_ratio = float(np.mean(valid_ratios))
    return mean_ndvi, outcome.selected, outcome.rejected, mean_valid_ratio


def _run_ndvi_snapshot(provider: DataProvider, request: AnalysisRequest) -> AnalysisResult:
    steps: list[ProcessingStep] = []
    mean_ndvi, selected, rejected, valid_ratio = _period_ndvi_mean(
        provider, request, request.date_range, steps, label="current"
    )

    if mean_ndvi is None:
        return _no_data_result(request, selected, rejected, steps)

    metric = Metric(name="NDVI", current_value=round(mean_ndvi, 4), unit="index")
    quality = DataQuality(
        scenes_used=len(selected),
        scenes_rejected=len(rejected),
        cloud_threshold=request.cloud_threshold,
        valid_pixel_ratio=valid_ratio,
    )
    evidence = Evidence(
        scenes=selected + rejected,
        formula=NDVI_FORMULA,
        processing_steps=steps,
        bands_used=["red", "nir"],
    )
    return AnalysisResult(
        analysis_type=request.analysis_type,
        status="success",
        metric=metric,
        data_quality=quality,
        evidence=evidence,
        limitations=[_ndvi_limitation()],
    )


def _run_ndvi_change(provider: DataProvider, request: AnalysisRequest) -> AnalysisResult:
    assert request.comparison_range is not None  # enforced by AnalysisRequest validator
    steps: list[ProcessingStep] = []

    current_mean, cur_selected, cur_rejected, cur_ratio = _period_ndvi_mean(
        provider, request, request.date_range, steps, label="current"
    )
    prev_mean, prev_selected, prev_rejected, prev_ratio = _period_ndvi_mean(
        provider, request, request.comparison_range, steps, label="comparison"
    )

    selected = cur_selected + prev_selected
    rejected = cur_rejected + prev_rejected

    if current_mean is None or prev_mean is None:
        missing = "current period" if current_mean is None else "comparison period"
        return _no_data_result(
            request,
            selected,
            rejected,
            steps,
            message_override=(
                f"No usable satellite observations were found for the {missing}. "
                "Try expanding the date range, increasing the cloud threshold, "
                "or selecting a larger area."
            ),
        )

    try:
        change = percentage_change(current=current_mean, previous=prev_mean)
    except ValueError as exc:
        return AnalysisResult(
            analysis_type=request.analysis_type,
            status="failed",
            message=f"Could not compute percentage change: {exc}",
            evidence=Evidence(
                scenes=selected + rejected, formula=NDVI_FORMULA, processing_steps=steps
            ),
            limitations=[_ndvi_limitation()],
        )

    metric = Metric(
        name="NDVI",
        current_value=round(change.current_value, 4),
        comparison_value=round(change.comparison_value, 4),
        absolute_change=round(change.absolute_change, 4),
        percentage_change=round(change.percentage_change, 2),
        unit="index",
    )
    ratios = [r for r in (cur_ratio, prev_ratio) if r is not None]
    quality = DataQuality(
        scenes_used=len(cur_selected) + len(prev_selected),
        scenes_rejected=len(cur_rejected) + len(prev_rejected),
        cloud_threshold=request.cloud_threshold,
        valid_pixel_ratio=float(np.mean(ratios)) if ratios else None,
    )
    evidence = Evidence(
        scenes=selected + rejected,
        formula=NDVI_FORMULA,
        processing_steps=steps,
        bands_used=["red", "nir"],
    )

    limitations = [_ndvi_limitation()]
    if quality.scenes_used <= 1:
        limitations.append(
            "Result confidence is limited because only one usable observation "
            "contributed to at least one period."
        )

    return AnalysisResult(
        analysis_type=request.analysis_type,
        status="success",
        metric=metric,
        data_quality=quality,
        evidence=evidence,
        limitations=limitations,
    )


def _no_data_result(
    request: AnalysisRequest,
    selected: list[Scene],
    rejected: list[Scene],
    steps: list[ProcessingStep],
    message_override: str | None = None,
) -> AnalysisResult:
    message = message_override or (
        "No usable satellite observations were found for this area and date "
        "range. Try expanding the date range, increasing the cloud threshold, "
        "or selecting a larger area."
    )
    return AnalysisResult(
        analysis_type=request.analysis_type,
        status="failed",
        message=message,
        data_quality=DataQuality(
            scenes_used=len(selected),
            scenes_rejected=len(rejected),
            cloud_threshold=request.cloud_threshold,
        ),
        evidence=Evidence(
            scenes=selected + rejected, formula=NDVI_FORMULA, processing_steps=steps
        ),
        limitations=[_ndvi_limitation()],
    )


def _ndvi_limitation() -> str:
    return (
        "NDVI is a vegetation-vigor proxy derived from reflectance; a change in "
        "NDVI alone does not establish drought, irrigation failure, or "
        "soil-moisture decline."
    )
