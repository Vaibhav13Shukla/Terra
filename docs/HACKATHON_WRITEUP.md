# Terra — Hackathon Writeup

**First Commit × AWS** (SHIP IT track). Backend/EO/AI/infra built here;
frontend built separately by the team.

## 1. Problem

There is no shortage of open Earth Observation data — Sentinel-2 alone is
free, global, and updated every few days. The pain is the distance between
*"I have a question about a piece of Earth"* and *"here is the answer, and
here is exactly how it was computed"*: catalog discovery, cloud filtering,
CRS handling, band alignment, nodata masking, windowed raster access,
temporal comparison, and turning a raw index into something a non-specialist
can trust.

## 2. Who experiences it

Developers and technical teams building on top of EO data — agri-tech,
climate-tech, carbon/dMRV, environmental and infrastructure monitoring. Their
alternative today is Sentinel Hub, Copernicus Browser, or raw STAC + rasterio
— all of which expose data and processing primitives, not a
question-to-evidence-backed-answer workflow.

## 3. Existing workflow (today, without Terra)

Find the right dataset, understand the STAC catalog, find matching scenes,
check cloud cover, handle CRS/projection, clip to the area of interest,
handle nodata/cloud masking, compute the index, align two time periods,
visualize, and explain. Each step is well-documented in isolation; doing all
of them correctly, every time, for every question, is the actual cost.

## 4. Why not just use Copernicus Browser / Sentinel Hub?

Both already do a version of "data + processing API" extremely well. Terra's
differentiation is not "nobody does satellite analytics" — that would be
false. It's a narrower claim: turning a natural-language question into a
*reproducible, evidence-backed* answer, with the scene selection, the
formula, and the data-quality caveats all attached to the result rather than
left for the user to reconstruct.

## 5. Terra's solution

```
question -> intent -> STAC discovery -> quality filter -> windowed COG reads
        -> NDVI -> period comparison -> evidence -> explanation -> API
```

Example (from a real, live run against Sentinel-2 — see §8):

```
NDVI (Aug 2025 vs Jul 2025), central California farmland
current: 0.5613   comparison: 0.5624   change: -0.2%
8 scenes used, 32 rejected (4 least-cloudy of 20 per period kept)
"NDVI decreased 0.2% relative to the comparison period..."
```

Genuinely near-zero for this real AOI/period — which is itself evidence the
system reports what the data says rather than a canned narrative. The
reproducible demo scenario (fixtures, clearly labeled as such) uses a
synthetic ~18% decline to give a deterministic, always-available walkthrough.

## 6. What we built during the hackathon

Full backend + EO processing engine + AI orchestration + AWS infrastructure
as code, from a from-scratch repository (see git history):

- **Domain model** (Pydantic): AOI, DateRange, Scene, AnalysisRequest/Result,
  Evidence, DataQuality, AnalysisIntent, AnalysisJob — typed contracts
  everywhere, no ad hoc dicts crossing module boundaries.
- **NDVI processing engine** (pure numpy): reflectance scaling, SCL cloud
  masking, invalid-pixel handling, percentage-change math — unit-tested
  exhaustively.
- **Provider abstraction**: `DataProvider` interface + `Sentinel2Provider`
  (real, Earth Search STAC + windowed COG reads) + `FixturesProvider`
  (deterministic, offline).
- **Analysis engine**: orchestrates discovery -> quality filtering -> scene
  capping -> concurrent windowed reads -> NDVI -> comparison -> evidence.
  Zero AI involvement — see §9.
- **AI layer**: deterministic natural-language intent parser (default,
  always available) plus an optional Amazon Bedrock adapter with mandatory
  graceful fallback.
- **API**: FastAPI app (`/v1/analyses`, `/health`, `/v1/providers`), Lambda-
  ready via Mangum, auto-generated OpenAPI docs.
- **AWS infrastructure as code**: SAM template — API Gateway, Lambda
  (container image), DynamoDB, S3, optional Bedrock, CloudWatch, IAM least
  privilege.
- **Tests**: 83 tests total (unit/integration/contract) — 80 run by default,
  offline and deterministic; 3 are opt-in live-network tests against real
  Sentinel-2 data.

## 7. Technical architecture

See [docs/architecture.md](architecture.md) for the full breakdown and
[docs/adr/](adr/) for individual decisions.

## 8. AWS usage

API Gateway -> Lambda (container image, FastAPI/Mangum) -> DynamoDB (job
state) + S3 (results) + Bedrock (optional, explanation text) -> CloudWatch.
Every service answers "why does Terra need this?" — no service was added for
the architecture diagram. **Deploy is pending AWS credentials**, stated
plainly rather than claimed; the template is written and YAML-validated.
See [infra/README.md](../infra/README.md).

## 9. AI usage

Amazon Bedrock is used for exactly two things, both optional with automatic
deterministic fallback: mapping a question to a structured analysis intent,
and explaining an already-computed result in plain language. It never
computes a measurement — every NDVI value, every percentage change, every
data-quality statistic comes from `app.processing` / `app.services`, in
Python, tested independently of any LLM. This split is enforced by module
boundaries (`app.services.analysis_engine` imports neither
`app.agents.intent_parser` nor `app.agents.bedrock`), not just convention.

## 10. Data sources

Sentinel-2 L2A Cloud-Optimized GeoTIFFs, AWS Registry of Open Data, via the
Earth Search v1 STAC API (Element 84) — public, no API key, no manual
download. Only the AOI window of each asset is ever read; whole scenes are
never downloaded. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## 11. Results

The canonical demo (fixtures, deterministic) reproduces an ~18% NDVI decline
end-to-end through the real API. Separately, the full pipeline was run
against **live** Sentinel-2 data end-to-end through the actual running HTTP
server — not just the engine in isolation — and returned a correct,
scientifically consistent result with real evidence (scene IDs, S3 hrefs,
scale/offset). Two real bugs were found and fixed during that live
validation (wrong reflectance scale/offset; SCL/red-nir resolution
mismatch) — see [docs/RISKS.md](RISKS.md) and
[docs/adr/002-processing-runtime.md](adr/002-processing-runtime.md) for the
full account, including a 6.2x latency fix (116s to 18.6-26.1s across three
separate live runs — variance is network-bound) found the same way.

## 12. Testing

83 tests total (80 run by default, offline): unit (NDVI math, percentage
change, geometry validation, quality filtering, scene capping, intent
parsing, Bedrock fallback), integration (the full pipeline against
fixtures), contract (the API's request/response shapes and HTTP status
codes), plus 3 opt-in live-network tests against real
Sentinel-2 + Earth Search. See [evaluation/scenarios/README.md](../evaluation/scenarios/README.md)
for the required scenario coverage mapped to specific tests, including two of
the brief's own AI-evaluation examples pinned as regression tests.

## 13. What we learned

- **Test against live data early, not last.** The fixtures-based suite was
  100% green throughout, but two bugs that would have broken every real
  analysis (wrong reflectance conversion, mismatched raster resolutions)
  were invisible to it by construction — they only surfaced once the real
  provider was exercised end-to-end. Same story with latency: a
  synchronous-processing assumption that looked reasonable on paper failed
  outright against real STAC search volume, and was fixed with a measured,
  documented trade-off rather than an assumption.
- **Provider server-side pre-filtering can silently defeat downstream
  evidence.** Filtering cloud cover too aggressively at the STAC query level
  meant rejected scenes never reached the quality filter that is supposed to
  explain *why* they were rejected. Fixed by querying a wider server-side cap
  and making the quality filter the authoritative, evidence-producing
  decision point.

## 14. Limitations (honest)

- One analysis family in the MVP: NDVI snapshot/change. NDVI is a
  vegetation-vigor proxy; every result says so explicitly and never claims a
  causal determination (drought, irrigation failure) it cannot support.
- AWS deployment is written as code, YAML-validated, and documented step by
  step — but not applied, because this environment has no AWS credentials.
- Synchronous request processing works (measured, live-verified) but is
  close enough to API Gateway's 29-second timeout that the async worker
  Lambda architecture the brief originally specifies is the correct next
  step for guaranteed reliability at scale — documented in ADR 002, not
  built untested.

## 15. Future vision

Per the original MERU deck's roadmap: Phase 1 (this MVP) unified EO access
for one workflow; Phase 2 would add processing/fusion across providers
(Landsat/HLS behind the same `DataProvider` interface — a contained addition
by design, see ADR 001); Phase 3 is the deck's long-term geospatial
intelligence vision, explicitly out of scope here.
