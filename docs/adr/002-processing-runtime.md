# ADR 002 — Synchronous request processing, with concurrent scene reads

## Context

Terra's `POST /v1/analyses` runs the full discover → filter → read → NDVI →
compare pipeline. The brief's reference architecture (§26, §28) describes an
async job model: `POST` returns `{job_id, status: "queued"}` immediately, a
separate worker Lambda does the work, and the client polls `GET /jobs/{id}`.

We built the simpler version first: `POST` runs the pipeline synchronously
and returns the completed job. The job store's status model
(`CREATED → ... → COMPLETED/FAILED`) already matches the async design, so the
question was purely "is synchronous processing fast enough?" — not an
architectural rewrite either way.

## Measurement

Against live Sentinel-2 data (Earth Search STAC + `sentinel-cogs`), for the
canonical demo AOI/period (central California farmland, Aug 2025 vs Jul 2025):

| Configuration | Total time |
|---|---|
| No scene cap (search returns ~20 low-cloud scenes/period) | **>120s, timed out** |
| Capped to 4 least-cloudy scenes/period, read serially | **116.1s** |
| Capped to 4 scenes/period, read concurrently (ThreadPoolExecutor) | **18.6s** |

Same NDVI values in the serial and concurrent runs (0.5613 / 0.5624,
`scenes_used=8`, `scenes_rejected=32`) — the speedup is purely from
concurrency, correctness is unchanged.

The uncapped case is a real bug, not just slow: an AOI with abundant coverage
(this one) can return up to the search `limit` (20) scenes per period, and the
engine was reading every selected scene with no bound. Fixed in
`app.services.quality_filter.cap_scenes` — after quality filtering, keep only
the `MAX_SCENES_PER_PERIOD` (4) least-cloudy scenes; the rest move to
`rejected` with an explicit reason, so they stay visible in the evidence
panel instead of silently vanishing.

Per-scene cost is dominated by network + GDAL overhead per asset (~2-6s per
band read observed in isolation), not CPU — so scenes are good candidates for
concurrent reads. `app.services.analysis_engine._read_scene_ndvi` isolates one
scene's full read+NDVI computation; `_period_ndvi_mean` runs up to
`MAX_SCENES_PER_PERIOD` of these concurrently via `ThreadPoolExecutor`. Each
worker opens its own `rasterio` dataset handle (inside
`DataProvider.read_window`), so there's no shared mutable GDAL state across
threads.

## Decision

1. **Cap scenes read per period** (`MAX_SCENES_PER_PERIOD = 4` in
   `app.services.quality_filter`). This bounds worst-case cost regardless of
   how many low-cloud scenes an AOI has, and is a legitimate statistical
   choice — 4 independent observations is enough for a stable mean, and
   `data_quality.valid_pixel_ratio` still surfaces confidence.
2. **Read scenes concurrently within a period** (I/O-bound, not CPU-bound —
   measured 6.2x speedup, no correctness change).
3. **Keep synchronous request/response** for the hackathon MVP: 18.6s for a
   genuinely real two-period comparison is within API Gateway's 29s
   integration timeout and acceptable for an interactive demo. This is a
   deliberate, documented trade-off (§53): the simplest architecture that
   satisfies the measured requirement, not the "impressive" one.

## Consequences / honest limitation

18.6s has headroom but not a large margin under API Gateway's 29s hard limit,
and network/STAC latency is variable — a slower run is plausible. This is not
fully solved by anything in-process; the architecturally correct fix for a
guaranteed-reliable AWS deployment is the async worker Lambda the brief
originally specifies (§26, §28): `POST` enqueues and returns in milliseconds,
a separate worker Lambda (invoked async or via SQS) does the actual
processing, and the client polls. The job store interface
(`app.services.job_store.JobStore`) and status model already support this
without an API contract change — only the wiring inside `create_analysis` in
`app/api/main.py` would move from "call `run_analysis` inline" to "enqueue and
return." This is documented here rather than built, because building and
*not testing* an async Lambda-to-Lambda invocation without AWS credentials
would be worse than an honest limitation (§57 — no fake production behavior).

## Alternatives considered

- **Reduce `MAX_SCENES_PER_PERIOD` further (e.g. 2)** — makes worst-case
  latency lower but weakens the statistical basis of the mean and doesn't
  address the real fix if network conditions worsen. Rejected as a substitute
  for the real fix (async worker), kept as a possible tuning knob.
- **FastAPI `BackgroundTasks`** — would return the HTTP response immediately
  and continue processing after. Rejected: on AWS Lambda, execution is frozen
  once the response is returned, so a background task started this way is not
  guaranteed to complete — it would work locally (uvicorn keeps the process
  alive) but silently fail to finish once deployed. Using it would be
  demo-only trickery, not real behavior (§59).
