# Terra — Architecture

**Terra** (Latin for "Earth") — Earth Observation, without the plumbing.
This document explains the deployed system, the data flow, and the trade-offs
behind it. See also [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
(the original engineering audit/plan) and [docs/adr/](adr/) (individual
decisions in depth).

## 1. Product architecture

```
User (AOI + dates + question)
        |
        v
   Terra API  (FastAPI: /v1/analyses, /health, /v1/providers)
        |
        +--> intent resolution (question -> AnalysisType, or direct)
        |         deterministic by default; optional Bedrock (ADR 003)
        |
        v
   Analysis Engine  (deterministic, no AI -- app/services/analysis_engine.py)
        |
        +--> geometry validation (app/services/geometry.py)
        +--> provider.search()          -- STAC discovery
        +--> quality_filter.filter_scenes()  -- cloud/band checks, with reasons
        +--> quality_filter.cap_scenes()     -- bound worst-case cost (ADR 002)
        +--> provider.read_window() x N, concurrent -- windowed COG reads
        +--> processing/ndvi.py         -- reflectance, NDVI, statistics
        +--> percentage_change()        -- period comparison
        v
   AnalysisResult  (metric, data_quality, evidence, limitations)
        |
        +--> explanation (deterministic by default; optional Bedrock)
        v
   Job Store  (InMemoryJobStore locally; DynamoDBJobStore when TERRA_JOB_STORE=dynamodb)
        |
        v
   API response  /  GET /v1/analyses/{id}  /  GET /v1/analyses/{id}/evidence
```

## 2. Data flow

1. Client sends AOI (GeoJSON Polygon, WGS84), a date range (plus optional
   comparison range), and either a structured `analysis` type or a
   natural-language `question`.
2. If `question` is given, it is resolved to an `AnalysisIntent` — deterministic
   keyword rules by default (ADR 003), Bedrock optionally. Unsupported
   questions return HTTP 422 with a clear reason, never a guess (§37, §51).
3. The engine validates the AOI (self-intersection, area budget —
   `app/services/geometry.py`) and searches the selected `DataProvider` for
   candidate scenes per period.
4. `quality_filter` rejects scenes with unknown/excessive cloud cover or
   missing bands, each with a recorded reason; `cap_scenes` further bounds the
   read to the least-cloudy N (default 4) scenes per period.
5. Selected scenes' red/NIR/SCL bands are read as **AOI windows only** (never
   whole scenes, §18), concurrently across scenes (ADR 002). Reflectance
   scale/offset comes from STAC `raster:bands` metadata, not the COG's own
   GDAL tags — see `app/providers/sentinel2.py` for why that distinction was
   necessary (verified against live data).
6. NDVI is computed per scene with SCL-derived cloud/nodata masking (§17,
   `app/processing/ndvi.py`), averaged per period, then compared.
7. The full `AnalysisResult` — metric, data quality (scenes used/rejected,
   valid-pixel ratio), evidence (scene IDs, formula, processing steps), and a
   standing scientific-honesty limitation — is stored via the job store and
   returned.

## 3. AWS architecture

```
Amplify (frontend, built separately)
    |  HTTPS
    v
API Gateway (HTTP API)
    |
    v
Lambda (container image -- rasterio/GDAL exceed the zip size limit)
    |  FastAPI app via Mangum
    +--> DynamoDB (job state)     -- pay-per-request, TTL
    +--> S3 (results/evidence)    -- encrypted, private, 30-day lifecycle
    +--> Bedrock (optional)       -- bedrock:InvokeModel only, IAM-scoped
    v
CloudWatch (logs)          IAM (least privilege throughout)
```

Defined as code in [infra/template.yaml](../infra/template.yaml) (AWS SAM).
**Not yet deployed from this environment** — see
[infra/README.md](../infra/README.md) for the honest status and exact
deploy steps.

## 4. Provider abstraction

See [ADR 001](adr/001-provider-abstraction.md). One interface
(`app.providers.base.DataProvider`), two implementations today
(`Sentinel2Provider`, real; `FixturesProvider`, deterministic/synthetic). The
analysis engine never imports a specific provider.

## 5. AI architecture

See [ADR 003](adr/003-ai-orchestration.md). Deterministic by default for both
intent parsing and result explanation; Bedrock is optional and gracefully
falls back on any failure. The engine itself has zero AI involvement.

## 6. Processing architecture

See [app/processing/ndvi.py](../backend/app/processing/ndvi.py). NDVI =
(NIR-RED)/(NIR+RED), computed on reflectance (not raw DN — the Sentinel-2
L2A BOA offset does not cancel in the ratio and must be applied first).
Invalid pixels (nodata, zero-denominator, out-of-[-1,1], cloud/shadow/snow per
SCL) are masked, not zeroed. Every result reports valid-pixel ratio.

## 7. Security

- No secrets in git (`.gitignore` excludes `.env`, keys, credentials —
  verified with a repo-wide scan; see the Security section of the root README).
- IAM least privilege: the API Lambda's role is scoped to its own DynamoDB
  table, its own S3 bucket, and `bedrock:InvokeModel` — nothing else.
- Input validation throughout: GeoJSON structure and bounds (Pydantic +
  shapely), dates (ordering), analysis type (enum), provider name (registry
  lookup, 400 on unknown).
- CORS is currently permissive (`*`) for hackathon development; documented in
  `app/api/main.py` as needing tightening to the deployed frontend's exact
  origin.

## 8. Failure handling

Every external dependency can fail, and each has a defined behavior (§60):
invalid AOI results in `AnalysisError` and HTTP 400; no usable scenes in
either period results in a successful HTTP response with `status="failed"`
and a plain-English message (this is a legitimate outcome, not a server
error); unknown provider results in HTTP 400; missing job results in
HTTP 404; Bedrock unavailable results in a silent fallback to the
deterministic path, never a user-visible error.

## 9. Scalability

The provider/job-store interfaces are already async-deployment-shaped (ADR
002): moving from synchronous in-Lambda processing to an async worker Lambda
requires no change to `app.services.job_store.JobStore`'s contract or the
public API's request/response shapes — only the wiring inside
`create_analysis` in `app/api/main.py`. Not built in this session because it
could not be tested without AWS credentials (§57).

## 10. Trade-offs (summary)

| Decision | Alternative considered | Why this one |
|---|---|---|
| Python backend | TypeScript (matches frontend) | Mature geospatial toolchain (rasterio/GDAL); every code example in the brief is Python |
| Synchronous request processing, capped + concurrent scene reads | Async worker Lambda | Measured 18.6-26.1s across live runs for the real demo request after fixing two bugs found via live testing (the slowest run is 90% of API Gateway's 29s limit); async split is documented (ADR 002) but not built untested |
| Deterministic intent/explain by default, Bedrock optional | Bedrock-required | §61 mandates the core workflow not depend on Bedrock; also the only way to keep tests offline and deterministic |
| One real provider (Sentinel-2) plus one synthetic (fixtures) | Multiple real providers | §79: don't build a second provider at the cost of reliability; the abstraction (ADR 001) makes adding one later a contained change |
