"""Deterministic natural-language intent parser (§8, §37, §61).

Maps a user's question to a structured :class:`AnalysisIntent`. This is the
DEFAULT and always-available path — it must work with no network and no AWS
credentials, because the core scientific workflow must not depend on an LLM
(§61). A Bedrock-backed parser (app.agents.bedrock) can optionally replace or
supplement this for more flexible phrasing, but this module is what keeps
Terra fully functional when Bedrock is disabled or unavailable.

Deliberately simple keyword rules rather than a grammar/ML classifier: the
supported analysis surface is small (NDVI snapshot/change) and the brief is
explicit that "the system should NOT claim certainty" and must give "a clear
unsupported-request response" rather than improvising (§37).
"""
from __future__ import annotations

import re

from app.domain.models import AnalysisIntent, AnalysisType

# A question must reference vegetation/land-cover concepts to be in Terra's
# supported domain at all. Anything else (irrigation certainty, crop yield
# forecasts, siting decisions, etc.) is explicitly unsupported rather than
# guessed at (§37, §51).
_VEGETATION_KEYWORDS = (
    "vegetation", "ndvi", "green", "greenness", "crop health", "plant health",
    "vigor", "vigour", "foliage", "canopy", "field", "farm", "crop", "land cover",
)

# Presence of any of these implies a temporal comparison is being asked for.
_CHANGE_KEYWORDS = (
    "change", "changed", "compare", "comparison", "since", "over the last",
    "over the past", "increase", "increased", "decrease", "decreased",
    "declined", "decline", "improved", "improvement", "worse", "better",
    "trend", "versus", " vs ", "difference",
)

# Phrasing that asks for a determination Terra's single metric cannot support
# (definitive causal/operational claims). We still run the *analysis* — NDVI
# is still the closest supported proxy — but flag it so the caller can be
# extra explicit that no certainty is being claimed (§20, §37).
_OVERCLAIM_KEYWORDS = (
    "definitely", "for certain", "guarantee", "prove", "proves", "certain that",
)


def parse_intent(question: str, default_cloud_threshold: float = 20.0) -> AnalysisIntent:
    """Parse a natural-language question into a structured analysis intent.

    Returns an :class:`AnalysisIntent` with ``supported=False`` and a
    human-readable ``reason`` for questions outside Terra's supported analyses,
    rather than guessing (§51). Never raises on ordinary user text.
    """
    q = question.strip().lower()

    if not q:
        return AnalysisIntent(
            supported=False,
            reason="The question was empty. Try asking, for example, "
            "'How has vegetation changed in this area?'",
        )

    if not any(kw in q for kw in _VEGETATION_KEYWORDS):
        return AnalysisIntent(
            supported=False,
            reason=(
                "This question isn't about vegetation/land-cover analysis, "
                "which is what Terra currently supports. Terra currently "
                "supports: vegetation change (NDVI) and vegetation snapshot "
                "(NDVI). Coming later: moisture analysis, land-cover change."
            ),
        )

    analysis_type = (
        AnalysisType.NDVI_CHANGE
        if any(kw in q for kw in _CHANGE_KEYWORDS)
        else AnalysisType.NDVI_SNAPSHOT
    )

    overclaims = any(kw in q for kw in _OVERCLAIM_KEYWORDS)
    reason = None
    if overclaims:
        reason = (
            "This question asks for a definitive determination. Terra reports "
            "a measured NDVI change; it does not by itself prove causes such "
            "as irrigation failure, drought, or soil-moisture decline."
        )

    return AnalysisIntent(
        supported=True,
        analysis_type=analysis_type,
        cloud_threshold=default_cloud_threshold,
        reason=reason,
    )


# Reserved for a future, slightly richer parser (e.g. extracting an explicit
# "last N days" window from the question). Not wired in yet — the API layer
# is responsible for date_range today — but kept here as the natural home for
# it so date-window parsing doesn't end up ad hoc elsewhere.
_LAST_N_DAYS_RE = re.compile(r"last\s+(\d+)\s+days?")


def extract_last_n_days(question: str) -> int | None:
    """Best-effort extraction of an explicit '(over the) last N days' window."""
    match = _LAST_N_DAYS_RE.search(question.lower())
    return int(match.group(1)) if match else None
