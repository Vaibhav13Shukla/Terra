# Terra — Evaluation Scenarios (§36)

Ten deterministic scenarios covering the required range (not just happy
paths). Rather than duplicate a second harness, each scenario names the exact
test that exercises it — every one of these already runs in CI on every
`pytest` invocation, offline and deterministic (see root README).

| # | Scenario | Expected behavior | Covered by |
|---|---|---|---|
| 1 | Healthy vegetation, stable between periods | `status="success"`, small/near-zero percentage change | `tests/integration/test_analysis_engine.py::test_ndvi_snapshot_single_period` |
| 2 | Declining vegetation (canonical demo case) | `status="success"`, NDVI 0.50→0.41, ~-18% | `tests/integration/test_analysis_engine.py::test_ndvi_change_matches_canonical_example` |
| 3 | High-cloud scene present | Scene rejected with a specific cloud-cover reason, visible in evidence | `tests/unit/test_quality_filter.py::test_rejects_high_cloud` |
| 4 | No valid scenes for the requested window | `status="failed"` with a clear, actionable message — not an exception, not a fabricated result | `tests/integration/test_analysis_engine.py::test_no_scenes_returns_failed_not_exception` |
| 5 | Invalid geometry (self-intersecting / oversized AOI) | Rejected before any data access, with a specific reason | `tests/unit/test_geometry.py::test_self_intersecting_rejected`, `test_aoi_too_large_rejected` |
| 6 | Short / unusual date range | Handled by the same deterministic pipeline — no special-casing needed | `tests/unit/test_models.py::test_daterange_stac_format` |
| 7 | AOI with abundant coverage (many candidate scenes) | Capped to the N least-cloudy scenes per period; overflow recorded as rejected-with-reason, not silently dropped | `tests/unit/test_scene_cap.py` (all 3 cases); **also verified live** — see `docs/adr/002-processing-runtime.md` |
| 8 | Missing required band on a scene | Scene rejected, reason names the missing band | `tests/unit/test_quality_filter.py::test_rejects_missing_band` |
| 9 | Repeated identical query | Deterministic — identical output both times (idempotency, §29) | `tests/integration/test_analysis_engine.py::test_repeated_identical_query_is_deterministic` |
| 10 | Unsupported natural-language question | `supported=False` with a clear reason, not a guessed analysis (§37, §51) | `tests/unit/test_intent_parser.py::test_unrelated_question_is_unsupported`; at the API layer, HTTP 422 — `tests/contract/test_api.py::test_create_analysis_unsupported_question_returns_422` |

## AI evaluation (§37)

Two of the brief's own example prompts are pinned as regression tests:

- *"Tell me if this farm definitely needs irrigation"* — stays a supported
  vegetation analysis, but the system does **not** claim certainty; an
  explicit no-certainty caution is attached
  (`tests/unit/test_intent_parser.py::test_irrigation_certainty_question_flags_overclaim_but_still_supported`).
- *"Find the best place to build a nuclear reactor"* — **not** silently
  reinterpreted as a supported analysis; returns a clear unsupported response
  (`tests/unit/test_intent_parser.py::test_unrelated_question_is_unsupported`).

## Live-data validation (beyond the offline suite)

The scenarios above run against `FixturesProvider` (deterministic, offline)
by default. The real `Sentinel2Provider` is validated separately, opt-in, via
`pytest -m network` (`tests/integration/test_sentinel2_live.py`) — real STAC
discovery, real scale/offset extraction, real SCL/red-nir grid alignment, and
a plausibility check on the resulting NDVI. See
`docs/adr/002-processing-runtime.md` for the full live-timing investigation
that found and fixed two real bugs neither the fixtures-based suite nor a
single live smoke test would have caught on its own.

## Running the evaluation suite

```bash
cd backend
../.venv/Scripts/python -m pytest tests/unit tests/integration tests/contract -v
```
