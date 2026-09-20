# Terra — Handoff (read this first)

Written so anyone (or any Claude Code session) can continue without the original
chat. State: branch **`infra/aws-deploy-fixes`** is the newest work and is stacked
on `frontend/continue` (which is the previous session's
`claude/peaceful-gauss-osu4cl` — frontend + auth + async worker + CI + deploy
runbook — plus a later round of frontend fixes). `main` is behind both. Nothing is
merged to `main` yet — open a PR or fast-forward `main` before continuing.
`infra/aws-deploy-fixes` adds: the AWS deployment fixes and rewritten runbook
(see "AWS deployment readiness" below), async-mode progress in the web UI, a
static-export frontend build, Bedrock observability, and an offline-test safety
guard.
Everything described here is pushed; nothing lives only on one laptop/session
except each dev's local `.venv` / `node_modules`.

## What Terra is

"Earth Observation, without the plumbing." Question + area + dates in, an
evidence-backed satellite analysis out (NDVI change from Sentinel-2). Built for
the First Commit x AWS hackathon (SHIP IT track). Naming history: pitched as
MERU, briefly PRUTHVI, final name **Terra** (matches the GitHub repo). The local
folder may still be called `MERU`; content is all Terra. The original pitch deck
(`Meru_Adil_Aniket.pdf/.pptx`) sits outside the repo in the parent folder.

## Status

**Backend: done and verified offline; not yet deployed.** 140 tests (137
offline + 3 opt-in live-network), ruff
clean, live-verified against real Sentinel-2 data through the running API
(that verification predates this round's changes; re-verify auth/async/CORS
against a real deploy — see `docs/DEPLOYMENT.md`).

| Area | State |
|---|---|
| Domain model, NDVI engine, geometry, quality filter, scene cap | done, tested |
| Providers: `Sentinel2Provider` (real) + `FixturesProvider` (deterministic) | done |
| Analysis engine (concurrent scene reads) | done, live-verified |
| Intent parser + explainer (deterministic default) + optional Bedrock adapter | done, fallback tested |
| API: `/health`, `/v1/providers`, `/v1/scenes`, `/v1/analyses` (+ GET list/id/evidence) | done |
| Auth: Cognito JWT verification, `AUTH_ENABLED` toggle (off by default) | done, tested with a self-signed JWKS; never run against a real Cognito pool |
| Job store: in-memory + DynamoDB (`TERRA_JOB_STORE=dynamodb`) | done; DynamoDB tested via fake table only |
| Async processing: SQS enqueue + worker Lambda (`TERRA_PROCESSING_MODE=async`) | done, tested with an in-memory fake queue/SQS event; never run against real SQS |
| CORS: configurable allowed origins (`CORS_ALLOW_ORIGINS`), security response headers | done |
| Structured logging, bounded retry/backoff, HTTP timeouts | done |
| IaC (SAM template: API + worker Lambda, Cognito, SQS+DLQ, throttling) | written; `cfn-lint`-clean **with the SAM transform**; defects found and fixed on `infra/aws-deploy-fixes` (see below); **NOT deployed**, image never built (no Docker/SAM here) |
| CI (GitHub Actions: ruff + pytest + cfn-lint + frontend lint/build, on push to `main` / PRs) | written, **never run**; `ruff format --check` will fail (see item 2 below) |
| Docs: architecture, ADR 001/002/003, RISKS, HACKATHON_WRITEUP, eval scenarios, `docs/DEPLOYMENT.md` runbook, `docs/FRONTEND_DESIGN.md` | done |

**Frontend: built in this repo now (`frontend/`), not "separate" anymore —
see the "Frontend" section below.** `next lint` and `next build` are clean, and
this session it was driven end to end in a real browser against a running local
backend: demo field -> fixtures analysis (-18.0%), a freehand-drawn area -> live
Sentinel-2 analysis (real result), the no-data path, history, and the copy-paste
curl (re-run and confirmed to reproduce the identical result). It has **not**
been run against a deployed backend or a real Cognito pool.

## What is NOT done (in priority order)

1. **Merge `frontend/continue` into `main`** (or open a PR and review it
   first) — everything in this handoff is on that branch only. It is a linear
   descendant of `main`, so a fast-forward works with no conflicts.
   `git fetch && git checkout frontend/continue` to get it.
2. **CI has never run, and the first PR will go red on `ruff format`.** The
   workflow triggers only on pushes to `main` and on pull requests, and the
   feature branch was pushed without a PR (`gh run list` returns nothing).
   Its `ruff format --check app tests` step fails locally: **42 backend files
   would be reformatted** (e.g. a blank line after module docstrings — real
   style drift, not a Windows artifact). Two honest options: run
   `ruff format app tests` in ONE dedicated commit before any other backend work
   (big diff, so do it when nobody else has backend changes in flight), or drop
   the format step from CI. It was deliberately NOT done here: it touches ~42
   backend files and would be a merge-conflict magnet. The Python lint/test
   steps and the new frontend job are unaffected. The frontend job (Node 22,
   `npm ci`, lint, build) uses exactly the commands verified locally but has not
   yet run on GitHub's runners.
3. **AWS deploy** — needs someone's AWS credentials. Full step-by-step:
   `docs/DEPLOYMENT.md` (account setup, Bedrock model access, Cognito test
   user, first deploy, smoke test, cost controls, teardown). This is also the
   first real test of `DynamoDBJobStore.from_table_name`, the container
   build, Cognito verification against a real pool, SQS enqueue/consume, and
   Bedrock model access — budget time for surprises, same as before.
4. **Deploy the frontend** — it exists (`frontend/`) but has never been
   deployed anywhere; it only ran in a throwaway dev-server session with no
   public URL. Fastest path: https://vercel.com/new, import this repo, set
   **Root Directory to `frontend`**, deploy. Then set its env vars
   (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_COGNITO_USER_POOL_ID`,
   `NEXT_PUBLIC_COGNITO_APP_CLIENT_ID` — see `frontend/.env.local.example`)
   once the backend is deployed (step 3) and redeploy.
5. **Wire the two together**: once both are deployed, redeploy the backend
   with `FrontendOrigin=<the real Vercel/custom domain>` (defaults to `*` —
   `docs/DEPLOYMENT.md` Part E6), and set the frontend's env vars to point at
   the real `ApiUrl`/Cognito ids from the SAM deploy outputs.
6. **Demo video** (<=3 min, judging gives no credit for what isn't shown).
   Plan: fixtures path first (deterministic ~18% NDVI decline), then one live
   Sentinel-2 run to show it's real. Say out loud which is which. The live result
   is genuinely near-zero change (-0.2%) for the demo AOI; that is honest, not a bug.
7. Decide whether to flip `AuthEnabled=true` before submission (depends on
   whether the hackathon rubric rewards real user auth, and whether the
   frontend's login flow is ready — `docs/DEPLOYMENT.md` Part G; note it has no
   per-user job isolation, so it implies more privacy than the system provides).
8. **Live-analysis latency vs. drawn area** (measured this session, synchronous
   mode, live Sentinel-2): the ~25 km² demo field takes ~20-30 s, but a
   hand-drawn ~47 km² area took **~200 s**, and a second concurrent request
   failed at 51 s with GDAL's "Read failed". Latency grows much faster than
   area, and a deployed API Gateway kills synchronous requests at 29 s. The
   frontend now shows the area, warns above ~30 km² for live imagery, and turns
   the raw 502 into an actionable message — but that only manages the symptom.
   The real fix is already written: `TERRA_PROCESSING_MODE=async` (SQS + worker
   Lambda; the UI already polls), plus a tighter AOI cap for live mode
   (backend allows 2500 km² today — `MAX_AOI_AREA_KM2` in
   `backend/app/services/geometry.py`). Neither has run against real AWS.
9. Swap the map basemap before any *commercial* launch: it now uses the
   keyless Sentinel-2 cloudless 2020 mosaic from EOX (real imagery, matches
   what Terra analyses), which is **CC BY-NC-SA 4.0** — fine for this
   hackathon, not for commercial use. Get a MapTiler/Mapbox key and change
   `BASEMAP` in `frontend/components/AOIMap.tsx`. Attribution is rendered and
   listed in `THIRD_PARTY_NOTICES.md`.

## AWS deployment readiness (branch `infra/aws-deploy-fixes`)

**The step-by-step runbook is `docs/DEPLOYMENT.md`** (every terminal command, with
what to expect at each step). It was rewritten because the old one would have
failed. **None of it has run against a real AWS account** — no SAM CLI or Docker
was available where it was written. Expect the first deploy to surface something.

Defects found by reading the template against how API Gateway/SAM/Lambda work,
each reproduced or verified offline, then fixed:

| Defect | Effect | Fix |
|---|---|---|
| Named API stage (`/dev`) | every route, `/health` included, returned 404 (FastAPI/Mangum don't strip the stage) | `$default` stage; `ApiUrl` has no prefix; regression test `tests/contract/test_lambda_handler.py` drives the real handler with API Gateway v2 events |
| Hard-coded `ImageUri` to a repo nothing created | first deploy could not find an image | removed; `Metadata` on both functions; `sam deploy --resolve-image-repos` |
| Worker timeout was an inherited 60 s | live jobs take up to ~200 s: killed, redelivered 3x, dead-lettered | worker 300 s, API 30 s, SQS visibility 1800 s |
| No `.dockerignore` | build context = repo root (~300 MB `.venv`, `node_modules`, `.git`) | root `.dockerignore` |
| Bedrock IAM unconditional, and only `foundation-model/*` in one region | comment said conditional; inference-profile model ids would AccessDeny | `Fn::If` on `BedrockOn`; profile + cross-region foundation-model resources; one action only |
| Cognito client had no CLI-testable flow | token could only be minted via the console | added `ALLOW_ADMIN_USER_PASSWORD_AUTH` (IAM-credential-only) |
| `explain()` swallowed Bedrock failures silently | a mis-configured Bedrock looked identical to a working one | logs `bedrock_explain_ok` / `bedrock_explain_fallback` (+ reason) |
| Frontend: async jobs showed a bare badge; polling died on the first failed poll | UI looked frozen / job stranded on "created" | queued/analysing panel; 8-failure tolerance, then an honest "lost contact" message |
| Static export wrote `/workspace.html` | hard refresh on any route 404s on static hosts | `output: "export"` + `trailingSlash: true` |

Decisions taken (so nobody re-litigates them): region `us-west-2` (Sentinel-2 is
there); frontend on **Amplify** (manual zip deploy); **`AuthEnabled=false` for the
demo**; **no Strands**; deploy **sync first, then async**.

Things to know that are easy to miss:

- **Bedrock only writes the explanation text.** The API parses questions with the
  deterministic parser; `parse_intent_bedrock` exists but `app/api/main.py` does not
  call it. The root README and write-up used to claim otherwise (and "Strands");
  corrected.
- **No per-user job isolation** — with auth on, any signed-in user can list every job.
- **The S3 results bucket is provisioned but unused.**
- **Test-suite safety.** Installing `aws-sam-translator` (for cfn-lint) pulls in
  `boto3`; two Bedrock tests that assumed boto3 was absent then made two real,
  rejected `InvokeModel` calls under the developer's default AWS profile. Fixed:
  `backend/tests/conftest.py` hides every credential source and blocks botocore
  HTTP for the whole suite, and those tests now simulate a missing boto3
  explicitly. Lesson: a test run is an AWS action too. Always pass an explicit
  `--profile` for the Terra account; never rely on a default profile.

## Run it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements-dev.txt   # Windows
cd backend
../.venv/Scripts/python -m pytest              # 127 offline tests
../.venv/Scripts/python -m pytest -m network   # 3 live tests (real Earth Search + COGs)
../.venv/Scripts/python -m ruff check app tests
../.venv/Scripts/python -m uvicorn app.api.main:app --port 8000
```

`boto3` is intentionally not required locally (Bedrock/DynamoDB code lazy-imports
it and degrades gracefully). If pip times out on it, that's a flaky network, not a bug.

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in Cognito ids once you have them
npm run dev                        # http://localhost:3000
```

The landing page and auth screens work with no backend running; `/workspace`
needs the backend up (`NEXT_PUBLIC_API_URL`, defaults to `http://localhost:8000`).
With no Cognito ids in `.env.local` the workspace runs in open "Demo mode" (no
sign-in) — that is the intended local/dev experience, not a bug. `npm run dev`
and `npm run build` first run `scripts/copy-maplibre-worker.mjs` (npm
`predev`/`prebuild`), which copies MapLibre's worker into `public/maplibre/`
(git-ignored) — without it the AOI overlay silently never draws.

## Frontend (what exists, what doesn't)

`frontend/` is a Next.js 16 (App Router, Turbopack) app — landing page +
Cognito auth + AOI-drawing workspace. Design spec: `docs/FRONTEND_DESIGN.md`.
Stack: Tailwind v4, Framer Motion, React Three Fiber (the landing page's
wireframe-globe hero), MapLibre GL JS, `amazon-cognito-identity-js`, Zustand.

- `lib/types.ts` and `lib/api.ts` are hand-typed against
  `backend/app/domain/models.py` / `docs/openapi.json` — keep them in sync
  manually if the API contract changes; nothing generates them automatically.
- `lib/auth.ts` wraps Cognito's SRP flow via `amazon-cognito-identity-js`.
  Untested against a real pool — the deployed app client only allows
  `ALLOW_USER_SRP_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` (see
  `infra/template.yaml`'s `TerraUserPoolClient`), which is what this library
  uses, so it should work, but budget time for the first real login to
  surface something.
- The workspace's map (`components/AOIMap.tsx`) draws an AOI by
  click-to-add-vertex, double-click to close — no undo/edit-vertex UI. It is
  MapLibre on the keyless Sentinel-2 cloudless mosaic (see item 9 above for
  the licence caveat), renders the AOI from the store (`lib/workspaceStore.ts`
  is the single source of truth), and frames the demo field on load.
- The analysis panel is split into `components/QuestionForm.tsx` (demo-field
  preset, question, dates, provider, live `/v1/scenes` observation preview,
  area + large-area warning), `ResultView.tsx` (headline, explanation, data
  quality, limitations, how-it-was-produced, evidence, curl, JSON),
  `HistoryList.tsx` (`GET /v1/analyses`) and a thin `InspectorPanel.tsx`
  (tabs + polling). Everything shown comes from fields the API returns; fixture
  results always carry a "not live imagery" banner. Demo AOI/dates live in
  `lib/demo.ts` (one place, on purpose — fixtures only have Jul-Aug 2025).
- Verified in a real browser against a local backend (see the Status section).
  Not verified: a deployed backend, real Cognito, mobile/small screens (the
  panel is a fixed 380 px column), and the async/polling path against real SQS.
- The frontend has no automated tests yet (no Vitest/Playwright specs) — the
  verification above was manual. Adding a couple of Playwright specs for the
  demo path (load demo field -> run -> expect -18.0%) would be the highest-value
  next test. CI (`.github/workflows/ci.yml`) gained a frontend lint + build job
  this session — but see "CI has never run" in the priority list below.

## Demo AOI (verified live to have 17-20 low-cloud scenes per period)

bbox `[-120.60, 36.95, -120.55, 37.00]` (central California farmland),
current `2025-08-01..2025-08-31`, comparison `2025-07-01..2025-07-31`,
provider `sentinel-2-l2a` (real) or `fixtures` (deterministic).

## New in this round (auth, async worker, CI, deploy runbook)

- **`requirements.txt` no longer lists `boto3`.** It was declared as a hard
  dependency but every test/docstring in this repo assumed boto3 was
  *absent* from the default dev env (that's how `test_bedrock_fallback.py`
  exercises the "boto3 not installed" path). Installing dev deps used to
  silently break that test. boto3 isn't needed locally anyway — the Lambda
  base image (`public.ecr.aws/lambda/python`) ships it already.
- **Cognito auth (`app/auth/`)** verifies JWTs against the pool's public JWKS
  over plain HTTPS — no AWS SDK, no credentials, so it's independently
  testable offline (`tests/unit/test_auth.py` builds a real RSA keypair and
  signs test tokens, no mocking of the crypto itself). Off by default
  (`AUTH_ENABLED=false`); `/health`, `/v1/providers`, `/v1/scenes` stay
  public even when enabled — only the analyses endpoints are gated.
- **Async worker (`app/worker/handler.py`, `app/services/analysis_queue.py`)**
  follows the exact same lazy-import-boto3 + Protocol + fake-object pattern
  as `DynamoDBJobStore`, specifically so it stays boto3-free for tests. A
  message that fails processing resolves the job to FAILED rather than
  re-raising (so one bad request can't become a poison-pill message); only a
  JobStore-level failure propagates so SQS can retry/DLQ it.
- Both features are new-code-tested but **never run against real AWS** — the
  same honest limitation this repo has applied to DynamoDB from the start.
  Don't claim them "verified" until `docs/DEPLOYMENT.md` Parts C/D/G have
  actually been run once.

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
- **Next.js 16 broke `create-next-app`'s own defaults**: `next/dynamic` with
  `ssr: false` is no longer allowed inside a Server Component — the landing
  page needed `"use client"` at the top. `maplibre-gl`'s package has no
  default export (v6+) — import named exports (`{ Map, NavigationControl }`),
  not `import maplibregl from "maplibre-gl"`. The new stricter
  `react-hooks/purity` ESLint rule flags `Math.random()` inside `useMemo`
  (used for the starfield) as an "impure render" — moved that generation to
  module scope instead, run once at import time.
- **A 3D hero can eat its own headline.** The globe under the landing page's
  H1 first shipped at full opacity/size and made the text unreadable —
  caught by actually screenshotting it (not just "it compiles"), fixed with
  lower wireframe opacity, fewer segments, a `position` offset pushing the
  globe down, and a radial-gradient scrim behind the text.
- **`whileInView` (Framer Motion) content looks broken in a naive full-page
  screenshot** — it renders at `opacity: 0` until actually scrolled into
  view (IntersectionObserver-driven), so a single `fullPage` screenshot
  without incremental scrolling shows empty boxes below the fold. Not a bug;
  scroll the page (or screenshot in viewport-sized chunks) to verify it.
- **This sandboxed session has no way to expose a public URL.** Outbound
  network only — no port-forwarding/tunnel tool exists here, regardless of
  GitHub/other access grants (those are unrelated capabilities). `npm run
  dev` only proves the app renders inside the session (verified via
  Playwright + a local Chromium at `/opt/pw-browsers/chromium`, matched to
  a matching `playwright-core` version installed with `--no-save` so it
  never touched `package.json`/lockfile). A real preview link requires an
  actual deploy (Vercel) or running it on your own machine.
- **This session's egress proxy blocks domains by org policy, not
  transiently** — `styles.refero.design`, `api.refero.design`, and
  `demotiles.maplibre.org` (the map's tile source) were all rejected with a
  403 at the proxy level from inside this sandbox. That's this sandbox's own
  policy; it does not mean these services are broken or blocked for a real
  deployed frontend running on someone's own machine/Vercel. (Confirmed later
  from an unrestricted machine: the map tile sources load fine.)
- **A map that "works" can still be missing its whole overlay layer.**
  MapLibre v6 runs GeoJSON sources in a web worker, found relative to its own
  `import.meta.url`. Turbopack rewrites that into `/_next/static/chunks/`,
  where the file doesn't exist, so the server answers with an HTML 404 and
  every GeoJSON layer (the drawn AOI) silently renders nothing — while the raster
  basemap, which needs no worker, looks perfectly healthy. The tell was one
  recurring console line: "Failed to load module script: … MIME type of
  text/html". Fixed by serving the worker from `public/` +
  `setWorkerUrl()` (`scripts/copy-maplibre-worker.mjs`, run by
  `predev`/`prebuild`). A screenshot-only check would never have caught it.
- **Don't trust the first plausible cause.** The AOI bug had two decoys: a
  `load`-vs-`style.load` event timing theory (a harmless improvement, not the
  cause) and, once I inspected the live map object, an apparently "stuck"
  animation. That last one was the test browser pane delivering zero
  `requestAnimationFrame` callbacks — an environment artifact, not an app bug;
  measure (`rAF` tick count) before concluding.
- **Latency scales with area faster than you'd hope.** See item 8 above:
  ~25 km² ≈ 20-30 s live, ~47 km² ≈ 200 s, and concurrent live requests can
  time out each other. Test the UI with a freehand-drawn area, not just the
  demo field.
- **Verify a shipped snippet by running it.** The "Use via API" curl is built
  from the job's stored request; it was executed against the backend and
  confirmed to return the identical result. Do the same after changing it.
- **The `config-protection` hook blocks edits to `eslint.config.mjs`.** When the
  copied MapLibre worker flooded ESLint with ~1,100 warnings, the answer was an
  `/* eslint-disable */` header written by the copy script — not loosening the
  shared config. Generated third-party code gets the header; our source stays
  fully linted.

## Conventions

Conventional Commits, push after each feature, honest limitations everywhere
(never claim an unrun checkbox), report scientifically honest language ("NDVI
decreased X%", never "the field is X% drier"). Full rules: `CLAUDE.md`. Ask an
advisor/reviewer pass before declaring a milestone done; it caught two blocking
bugs late in the build.

## Continuing from another laptop

Clone the repo and **check out `infra/aws-deploy-fixes`** (not `main` — this branch
is ahead of `main` and the entire frontend plus the AWS fixes only exist here; it
already contains everything on `frontend/continue`. Merge or PR it into `main`
first if you want `main` to be current; `claude/peaceful-gauss-osu4cl` is an
older subset of the same history). Create the backend
venv (`pip install -r backend/requirements-dev.txt`) and frontend
`node_modules` as above ("Run it"). An *existing* venv created before the auth
work needs a re-install too (`python-jose` is a new dependency). Open Claude Code in the repo folder; it loads `CLAUDE.md`, which points
here. The original chat transcript is not in git — this file and the code are
the entire handoff. Use your own Claude/GitHub account rather than sharing one
login (add collaborators on GitHub).
