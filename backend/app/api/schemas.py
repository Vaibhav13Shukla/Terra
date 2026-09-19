"""API-level request schemas (§43).

Kept separate from the internal domain model (`app.domain.models`) so the
public HTTP contract can evolve independently of internal representations —
e.g. accepting either a structured `analysis` type or a natural-language
`question`, which the domain's `AnalysisRequest` deliberately does not model
(that resolution is the API layer's job, not the engine's).
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.models import AOI, AnalysisType


class CreateAnalysisRequest(BaseModel):
    """POST /v1/analyses request body.

    Exactly one of ``analysis`` (direct, structured) or ``question``
    (natural-language, resolved via the intent parser) must be given.
    """

    model_config = ConfigDict(extra="forbid")

    aoi: AOI
    start_date: dt.date
    end_date: dt.date
    comparison_start_date: dt.date | None = None
    comparison_end_date: dt.date | None = None

    analysis: AnalysisType | None = Field(
        default=None, description="Direct analysis type; alternative to 'question'."
    )
    question: str | None = Field(
        default=None,
        description="Natural-language question; alternative to 'analysis'.",
        max_length=500,
    )

    cloud_threshold: float = Field(default=20.0, ge=0.0, le=100.0)
    provider: str = Field(default="sentinel-2-l2a")

    @model_validator(mode="after")
    def _exactly_one_of_analysis_or_question(self) -> CreateAnalysisRequest:
        if self.analysis is None and not (self.question and self.question.strip()):
            raise ValueError("either 'analysis' or 'question' must be provided")
        return self
