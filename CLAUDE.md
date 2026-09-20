# Terra — working notes for Claude Code

**New session or new laptop? Read [HANDOFF.md](HANDOFF.md) first** — current
status, what's left, how to run everything, and the hard-won lessons.

**Terra** = "Earth Observation, without the plumbing." Turns a natural-language
geospatial question into a reproducible, evidence-backed satellite analysis.
This repo is **backend + EO engine + AI orchestration + AWS infra + tests +
frontend**. `frontend/` is a Next.js app (3D/scroll-animated landing page +
Cognito auth + map workspace); see `frontend/README.md` and
`docs/FRONTEND_DESIGN.md` for its design spec.

## Golden rules (do not break)

1. **Deterministic science, LLM only for language.** The LLM (Bedrock) may
   explain results (and a Bedrock intent adapter exists, but the API currently
   parses questions deterministically). It NEVER computes NDVI, cloud cover, or
   any measurement. All numbers come from `app/processing` and
   `app/services` in Python.
2. **Scientific honesty.** Report "NDVI decreased X%", never "the field is X%
   drier." Always surface data quality (scenes used/rejected, cloud, valid-pixel
   ratio) and limitations.
3. **Windowed reads only.** Read the AOI window of a COG, never a whole scene.
4. **Works offline.** The default `pytest` run needs no network and no AWS
   credentials. Bedrock and AWS adapters degrade gracefully (deterministic intent
   parser; in-memory job store; fixtures provider).
5. **No secrets in git.** `.env`, keys, credentials are git-ignored.

## Layout

- `backend/app/domain/models.py` — Pydantic contracts (AOI, DateRange, Scene,
  AnalysisRequest/Result, Evidence, DataQuality, AnalysisJob). Cross-module data
  is always one of these, never a bare dict.
- `backend/app/processing/ndvi.py` — pure numpy NDVI + percentage change.
- `backend/app/services/` — geometry, quality filter, analysis engine, job store.
- `backend/app/providers/` — `DataProvider` base + `sentinel2` (Earth Search) +
  `fixtures` (deterministic). Registry keyed by name; engine is provider-agnostic.
- `backend/app/agents/` — deterministic intent parser + optional Bedrock adapter.
- `backend/app/auth/` — Cognito JWT verification + the FastAPI auth dependency.
  Off by default (`AUTH_ENABLED=false`); see `app/auth/dependencies.py`.
- `backend/app/services/analysis_queue.py`, `backend/app/worker/` — optional
  async processing (`TERRA_PROCESSING_MODE=async`): SQS enqueue + a worker
  Lambda that runs the same pipeline as the synchronous API path.
- `backend/app/api/` — FastAPI app (`/v1/analyses`, `/health`), Lambda via Mangum.
- `infra/` — SAM template (API + worker Lambda, Cognito, SQS+DLQ).
- `docs/DEPLOYMENT.md` — step-by-step AWS deployment runbook.
- `docs/FRONTEND_DESIGN.md` — frontend design spec (tokens, layout, components).
- `frontend/` — Next.js app: landing page, Cognito auth, AOI-map workspace.
- `evaluation/` — deterministic scenarios.

## Commands

```bash
cd backend
../.venv/Scripts/python -m pytest              # all tests (offline, deterministic)
../.venv/Scripts/python -m pytest -m network   # live STAC test (opt-in)
../.venv/Scripts/python -m ruff check app tests
../.venv/Scripts/python -m ruff format app tests
```

## Conventions

- Python 3.11, type hints, ruff (E,F,I,UP,B,W). Conventional Commits
  (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Push after each feature.
- Add a new `AnalysisType` only with matching processing code AND tests.
