"""Deterministic, template-based result explanation (§8, §61).

Turns an :class:`AnalysisResult` into a short natural-language summary using
ONLY the values already computed by the deterministic engine — never inventing
observations or claims (§18 in the natural-language section: "explain the
result and evidence" is the LLM's job, but the numbers themselves are not).

This is the default/fallback explainer used when Bedrock is disabled or
unavailable, so the core workflow is never blocked on an LLM call (§61).
"""
from __future__ import annotations

from app.domain.models import AnalysisResult


def explain_result(result: AnalysisResult) -> str:
    """Produce a plain-English explanation of ``result``.

    Uses only fields already present on the result — no external knowledge,
    no speculation beyond the stated limitations.
    """
    if result.status == "failed":
        return result.message or "The analysis could not be completed."

    if result.metric is None:
        return "The analysis completed but produced no metric."

    m = result.metric
    lines: list[str] = []

    if m.percentage_change is not None:
        direction = "decreased" if m.percentage_change < 0 else "increased"
        lines.append(
            f"{m.name} {direction} {abs(m.percentage_change):.1f}% relative to "
            f"the comparison period (from {m.comparison_value:.3f} to "
            f"{m.current_value:.3f})."
        )
    else:
        lines.append(f"{m.name} is {m.current_value:.3f} for the selected period.")

    if result.data_quality is not None:
        dq = result.data_quality
        lines.append(
            f"Based on {dq.scenes_used} usable satellite observation"
            f"{'s' if dq.scenes_used != 1 else ''}"
            f"{f' ({dq.scenes_rejected} rejected for quality)' if dq.scenes_rejected else ''}."
        )
        if dq.scenes_used <= 1:
            lines.append(
                "Result confidence is limited because only one usable "
                "observation contributed to this result."
            )

    for limitation in result.limitations:
        lines.append(limitation)

    return " ".join(lines)
