# Terra

**Earth Observation, without the plumbing.**

Terra (Latin for "Earth") turns a natural-language geospatial question into a
reproducible, **evidence-backed** satellite analysis. You give it an area, a
time range, and a question; Terra discovers the right Sentinel-2 imagery, filters
out unusable scenes, computes the metric from the actual pixels, compares periods,
and shows exactly how it got the number.

> Built for the **First Commit × AWS** hackathon (SHIP IT track).
> Frontend is developed separately by the team; **this repository is the backend,
> Earth-Observation processing engine, AI orchestration, tests, and AWS infrastructure.**

---

## The problem

There is no shortage of open satellite data. The pain is the journey from
*"I have a question about this piece of Earth"* to *"here is the answer, and here
is exactly how it was computed"* — catalog search, cloud filtering, CRS handling,
band alignment, nodata masking, windowed raster reads, temporal comparison. Terra
abstracts that plumbing behind one workflow and one API.

## The solution

```
Question ─▶ Intent ─▶ STAC discovery ─▶ quality filter ─▶ windowed COG read
        ─▶ cloud mask ─▶ NDVI ─▶ period comparison ─▶ evidence ─▶ explanation
```

Example result (real numbers come from the pipeline, never from the LLM):

```
NDVI change      ↓ 18.2%
current  0.41    previous 0.50
3 scenes used · 2 rejected · 8% median cloud cover
formula: (NIR - RED) / (NIR + RED)
```

Terra is deliberately **scientifically honest**: it reports *"NDVI decreased 18.2%
relative to the comparison period"*, not *"the field is 18% drier"*.

## Architecture

```
User ─▶ Amplify (frontend) ─▶ API Gateway (HTTP API) ─▶ API Lambda (FastAPI)
        │                                                   │
        │                                        ┌──────────┼───────────┐
        │                                        ▼          ▼           ▼
        │                                    DynamoDB   Bedrock+     Analysis
        │                                    (jobs)     Strands      Worker (Lambda
        │                                               (intent+     container)
        │                                               explain)         │
        │                                                    STAC ◀──────┤
        │                                          Sentinel-2 COG ◀──────┤
        │                                                     S3 ◀───────┘
        └──────────────────── CloudWatch (logs) · IAM (least privilege) ─┘
```

See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) and
[`docs/adr/`](docs/adr/) for the design and decisions.

### The AI split (non-negotiable)

| Layer | Responsibility |
|---|---|
| **LLM (Bedrock + Strands)** | natural language → structured intent; explain the result |
| **Deterministic Python** | geometry, dates, scene filtering, raster reads, NDVI, statistics, comparison |

The LLM never produces a scientific measurement. If Bedrock is unavailable, a
deterministic rule-based intent parser keeps the pipeline fully functional.

## AWS usage

| Component | Service | Purpose |
|---|---|---|
| Frontend hosting | Amplify | serves the team's web app |
| Public API | API Gateway (HTTP API) | `/v1/analyses`, `/health` |
| API + orchestration | Lambda | validate, create job, invoke worker |
| Raster/NDVI compute | Lambda (container image) | rasterio+GDAL exceed the zip limit |
| Job state | DynamoDB | analysis lifecycle |
| Results / evidence | S3 | result JSON, previews |
| AI | Bedrock + Strands | intent + explanation |
| Observability | CloudWatch | structured logs, latency |
| Infrastructure | SAM / CloudFormation | reproducible deploy (`infra/`) |
| Satellite data | Sentinel-2 L2A COG (AWS Open Data) | actual imagery — no API key |

## Data source

[Sentinel-2 L2A Cloud-Optimized GeoTIFFs](https://registry.opendata.aws/sentinel-2-l2a-cogs/)
on the AWS Registry of Open Data, discovered via the
[Earth Search v1 STAC API](https://earth-search.aws.element84.com/v1). Public,
no API key. Terra reads **only the AOI window** of each COG, never whole scenes.
See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for attribution.

## Repository layout

```
backend/
  app/
    domain/       # Pydantic domain model (the typed contracts)
    services/     # geometry, quality filter, analysis engine, job store
    providers/    # DataProvider abstraction + Sentinel-2 + fixtures adapters
    processing/   # pure NDVI + change math (numpy)
    agents/       # intent parser (deterministic) + Bedrock adapter, tools
    api/          # FastAPI app (API Gateway + Lambda via Mangum)
  tests/          # unit · integration · contract · e2e
infra/            # SAM template (container-image worker), scripts
docs/             # architecture, ADRs, hackathon writeup
evaluation/       # deterministic scenarios & fixtures
```

## Local development

Requires Python 3.11+.

```bash
cd backend
python -m venv ../.venv
../.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source ../.venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
python -m pytest            # unit/integration/contract/e2e (deterministic, offline)
python -m pytest -m network # optional: hits the live Earth Search STAC API
python -m uvicorn app.api.main:app --reload   # local API at http://127.0.0.1:8000
```

The default test run is fully deterministic and needs no network or AWS credentials.

## API (v1)

```
GET  /health
GET  /v1/providers
POST /v1/analyses                 # create an analysis job (question or structured)
GET  /v1/analyses/{id}            # poll job status / result
GET  /v1/analyses/{id}/evidence   # evidence for a completed analysis
```

Full request/response schemas are in the generated OpenAPI docs at `/docs` when the
API is running.

## Testing & evaluation

83 tests total. 80 run by default, fully offline and deterministic (no
network, no AWS credentials needed): unit tests cover NDVI math, percentage
change, geometry validation, schema rules, scene filtering/capping, intent
parsing, and the Bedrock adapter's mandatory graceful fallback. Contract
tests pin the API's request/response shapes and HTTP status codes. The
remaining 3 are opt-in (`pytest -m network`) and run against the real Earth
Search STAC API and live Sentinel-2 data — see
[`evaluation/scenarios/README.md`](evaluation/scenarios/README.md) for the
required scenario coverage (§36) mapped to specific tests, and
[`docs/adr/002-processing-runtime.md`](docs/adr/002-processing-runtime.md)
for what running against live data actually found (two real bugs, fixed and
regression-tested) and fixed (a 6.2x latency improvement, live-verified).

## Security

No secrets are committed — verified with a repo-wide scan for AWS access
keys, private key headers, and inline credentials (clean); `.gitignore`
excludes `.env`, keys, and credential files, and none are tracked (verified
via `git ls-files`). Deployed infrastructure uses IAM roles scoped to Terra's
own DynamoDB table, its own S3 bucket, and `bedrock:InvokeModel` only —
never `AdministratorAccess`. AWS credentials are never exposed to the
frontend.

## Deployment status

The AWS infrastructure is defined as code in [`infra/`](infra/) (AWS SAM;
YAML-validated). **Deploy is pending the team's AWS credentials** — not yet
applied from this environment. Deploy steps are documented exactly in
[`infra/README.md`](infra/README.md). The full application pipeline (not the
infrastructure — the actual discover→NDVI→evidence logic) has been verified
end-to-end against **live** Sentinel-2 data through the real running API
server, independent of any AWS deployment.

## AI coding tools

Built with the assistance of **Claude Code** (Anthropic). All satellite
measurements are computed deterministically in Python, not generated by an LLM.

## Limitations (honest)

- One analysis type in the MVP: **NDVI change** (plus NDVI snapshot). NDVI is a
  vegetation-vigor proxy; a decrease does not by itself prove drought or
  soil-moisture loss.
- Sentinel-2 revisit + cloud cover mean some AOI/date combinations have no usable
  observations; Terra says so rather than inventing an answer.

## License

MIT — see [`LICENSE`](LICENSE).
