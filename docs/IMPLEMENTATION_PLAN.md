# Terra — Engineering Audit & Implementation Plan

**Terra** (Latin for "Earth")
*Earth Observation, without the plumbing.*

Hackathon edition. Target: First Commit × AWS (SHIP IT track).
Author: Adil / Aniket (+ Claude Code as AI pair). Date: 2025-09-19.

---

## 1. Current state (audit)

- Fresh project. `Terra/` created as its own git repository (the parent
  `Hackathon/` folder is a junk drawer of unrelated projects — EPFO, claimready,
  subsidysetu; its root `package.json` belongs to the EPFO redesign, **not** Terra).
- No prior Terra code, infra, or tests exist. This is a genuine from-scratch build.
- Authoritative inputs: the 114-section Terra master brief and the pitch deck
  (`../Meru_Adil_Aniket.pdf`, the original pitch deck). The brief is a superset of the deck for everything
  built now; the deck is revisited for visual identity when the frontend lands.

## 2. Feasibility spike (done first, before any architecture)

The single highest risk was: *do windowed COG reads over HTTP actually work from
this machine?* A throwaway spike (`spike_cog.py`, since deleted) confirmed:

| Check | Result |
|---|---|
| `rasterio` 1.4.4 / GDAL 3.10.3 install on Windows | binary wheels OK |
| Earth Search v1 STAC (`sentinel-2-l2a`) search | 5 items, cloud < 20% |
| Asset keys `red` / `nir` / `scl` present | confirmed on live item |
| Windowed remote read of a small AOI | **259,794 px of 120,560,400 (0.2%)** in 8.3 s |
| WGS84 to scene CRS (EPSG:32610) reprojection | OK |

**Conclusion:** the discover -> window-read -> NDVI pipeline is viable. Build proceeds.

## 3. Proposed architecture (locked decisions)

- **Backend / processing: Python** (rasterio, pystac-client, numpy, shapely,
  Pydantic, pytest). Matches every code example in the brief and the mature
  geospatial toolchain. **Frontend: TypeScript/React** (template supplied later).
  Bridged by an OpenAPI contract.
- **Provider abstraction** (adapter pattern): `DataProvider` base + a real
  `sentinel-2-l2a` adapter (Earth Search) + a deterministic `fixtures` adapter so
  tests and the demo never depend on a live third party (§13).
- **AI split (mandatory, §8):** deterministic code does *all* geometry, dates,
  filtering, raster math, NDVI, statistics. The LLM only maps natural language ->
  a validated `AnalysisRequest` and explains results. A **deterministic rule-based
  intent parser is the default path**; Bedrock sits behind an interface and is
  optional — every test passes without AWS credentials (§61).
- **Lambda = container image** (rasterio+GDAL exceed the 250 MB zip limit; §Lambda).
- **Job model:** `POST /analysis` -> job id -> poll `GET /jobs/{id}` (§26).
- **Scientific honesty (§20):** Sentinel-2 L2A `raster:bands` scale/offset applied
  before NDVI (the post-2022 BOA offset does not cancel in the ratio); results are
  phrased as "NDVI changed X%", never "the field is X% drier".

## 4. AWS architecture

Amplify (frontend) -> API Gateway -> Lambda (container) -> {S3 results, DynamoDB jobs,
Bedrock intent/explain}. CloudWatch logs. Defined as code in `infra/template.yaml`
(SAM). **Deploy is pending the user's AWS credentials** — the IaC is written and
validated but not applied in this session; the README says so plainly (no §66
checkbox is ticked that wasn't actually run).

## 5. MVP scope (P0 -> cut lines)

- **P0:** AOI + date validation -> Sentinel-2 discovery -> cloud/quality filter ->
  windowed band reads -> NDVI (masked) -> period comparison -> evidence + API. Deterministic
  fixture path for the whole pipeline. End-to-end test.
- **P1:** FastAPI app + OpenAPI, job store, Bedrock intent/explain behind interface,
  SAM template, README/ADRs/writeup, evaluation scenarios.
- **P2 (only if P0/P1 excellent):** NDWI, second provider (HLS/Landsat), richer overlays.

## 6. Implementation sequence

1. Domain models (Pydantic) — **done**.
2. Geometry service (validate/normalize AOI, area guard) + tests.
3. NDVI + percentage-change processing (pure numpy) + tests.
4. Provider base + fixtures adapter + Sentinel-2 adapter + tests.
5. Quality filter (cloud/date/intersection/validity) + tests.
6. Analysis engine (orchestrates 2-5) + in-memory + DynamoDB job store + tests.
7. Deterministic intent parser + Bedrock adapter (interface, fallback) + tests.
8. FastAPI app (`/health /providers /scenes /analysis /jobs /results`) + contract tests.
9. E2E test (fixture path) + evaluation scenarios (§36).
10. Infra (SAM, container Lambda), README, ADRs, writeup, THIRD_PARTY_NOTICES.
11. Judge simulation + security sweep.

## 7. Testing strategy

Unit (geometry, NDVI, %-change, filter, schemas, intent parser), contract
(API + provider interface + agent tool schemas), integration (request->job->result on
fixtures), one deterministic E2E. A live-network test for the Sentinel adapter is
marked `@pytest.mark.network` and skipped by default so CI is deterministic.

## 8. Definition of done (per feature)

Code + tests + tests pass + error cases + docs updated + (where applicable) API works
+ demo/fixture path works. Incomplete work is marked explicitly; no fake production
behavior (§57-59).

## 9. Risks (top)

| Risk | Mitigation |
|---|---|
| Live EO API/network unavailable | fixtures adapter; network tests skipped by default |
| Lambda package size (GDAL) | container-image Lambda |
| No AWS creds this session | Bedrock optional + deterministic default; deploy documented, not faked |
| Raster read latency | windowed reads (0.2% of scene); async job model |
| Scientific overclaiming | scale/offset applied; honest metric phrasing; limitations surfaced |
