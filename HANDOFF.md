# Terra — Handoff (read this first)

Written so anyone (or any Claude Code session) can continue without the original
chat. State as of commit `fe282ae` on `main`. Everything described here is
pushed; nothing lives only on one laptop except the local `.venv`.

## What Terra is

"Earth Observation, without the plumbing." Question + area + dates in, an
evidence-backed satellite analysis out (NDVI change from Sentinel-2). Built for
the First Commit x AWS hackathon (SHIP IT track). Naming history: pitched as
MERU, briefly PRUTHVI, final name **Terra** (matches the GitHub repo). The local
folder may still be called `MERU`; content is all Terra. The original pitch deck
(`Meru_Adil_Aniket.pdf/.pptx`) sits outside the repo in the parent folder.

## Status

**Backend: done and verified.** 104 tests (101 offline, 3 live-network), ruff
clean, live-verified against real Sentinel-2 data through the running API.

| Area | State |
|---|---|
| Domain model, NDVI engine, geometry, quality filter, scene cap | done, tested |
| Providers: `Sentinel2Provider` (real) + `FixturesProvider` (deterministic) | done |
| Analysis engine (concurrent scene reads) | done, live-verified |
| Intent parser + explainer (deterministic default) + optional Bedrock adapter | done, fallback tested |
| API: `/health`, `/v1/providers`, `/v1/scenes`, `/v1/analyses` (+ GET list/id/evidence) | done |
| Job store: in-memory + DynamoDB (`TERRA_JOB_STORE=dynamodb`) | done; DynamoDB tested via fake table only |
| Structured logging, bounded retry/backoff, HTTP timeouts | done |
| IaC (SAM template, container Lambda, throttling) | written, YAML-validated, **NOT deployed** |
| Docs: architecture, ADR 001/002/003, RISKS, HACKATHON_WRITEUP, eval scenarios | done |

## What is NOT done (in priority order)

1. **Frontend** — team builds it separately. Contract: `docs/openapi.json`
   (regenerate with `python scripts/export_openapi.py` after any API change).
2. **AWS deploy** — needs someone's AWS credentials. Steps: `infra/README.md`.
   First real deploy is also the first real test of `DynamoDBJobStore.from_table_name`,
   the container build, and Bedrock model access. Budget time for surprises.
3. **Demo video** (<=3 min, judging gives no credit for what isn't shown).
   Plan: fixtures path first (deterministic ~18% NDVI decline), then one live
   Sentinel-2 run to show it's real. Say out loud which is which. The live result
   is genuinely near-zero change (-0.2%) for the demo AOI; that is honest, not a bug.
4. Tighten CORS from `*` to the deployed frontend origin (`app/api/main.py`, `infra/template.yaml`).
5. Do NOT build the async worker Lambda without AWS creds to test it. It is the
   documented next architectural step (ADR 002) but untested infra is worse than
   an honest limitation.

## Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements-dev.txt   # Windows
cd backend
../.venv/Scripts/python -m pytest              # 101 offline tests
../.venv/Scripts/python -m pytest -m network   # 3 live tests (real Earth Search + COGs)
../.venv/Scripts/python -m ruff check app tests
../.venv/Scripts/python -m uvicorn app.api.main:app --port 8000
```

`boto3` is intentionally not required locally (Bedrock/DynamoDB code lazy-imports
it and degrades gracefully). If pip times out on it, that's a flaky network, not a bug.

## Demo AOI (verified live to have 17-20 low-cloud scenes per period)

bbox `[-120.60, 36.95, -120.55, 37.00]` (central California farmland),
current `2025-08-01..2025-08-31`, comparison `2025-07-01..2025-07-31`,
provider `sentinel-2-l2a` (real) or `fixtures` (deterministic).

## Non-obvious lessons (each cost real debugging; don't relearn them)

- **Test against live data, not just fixtures.** Fixtures stayed green while two
  bugs would have broken every real run: (a) GDAL band tags report scale/offset
  `(1.0, 0.0)`; the real `(0.0001, -0.1)` is only in STAC `raster:bands`;
  (b) Sentinel-2 SCL is 20 m vs red/nir 10 m, so shapes mismatch and need
  nearest-neighbour alignment (`out_shape`).
- **Providers must not pre-filter by the user's exact cloud threshold**, or
  rejected scenes never reach the quality filter and can't show a rejection reason.
- **pystac_client wraps every failure into `APIError`** (original type discarded);
  only `status_code is None` or `>= 500` is transient. 4xx must not be retried.
- **Latency**: uncapped scene reads timed out (>120 s). Cap 4 scenes/period +
  concurrent reads gave 18.6-26.1 s across live runs (network-bound). The
  slowest is 90% of API Gateway's 29 s hard limit. Report the range, not the best run.
- Unexpected exceptions in `create_analysis` must resolve the job to `failed`
  (else it strands in `created` forever). Covered by a regression test.
- The LLM never computes a number. Deterministic code does all science; Bedrock is
  optional, only maps question->intent and explains results, with automatic fallback.

## Conventions

Conventional Commits, push after each feature, honest limitations everywhere
(never claim an unrun checkbox), report scientifically honest language ("NDVI
decreased X%", never "the field is X% drier"). Full rules: `CLAUDE.md`. Ask an
advisor/reviewer pass before declaring a milestone done; it caught two blocking
bugs late in the build.

## Continuing from another laptop

Clone the repo, create the venv as above, open Claude Code in the repo folder; it
loads `CLAUDE.md`, which points here. The original chat transcript is not in git.
Use your own Claude/GitHub account rather than sharing one login (add collaborators
on GitHub).
