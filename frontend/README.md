# Terra — Frontend

Next.js (App Router) frontend for Terra. Landing page + authenticated
workspace (AOI map, question form, evidence panel) wired against the
`backend/` FastAPI service.

Design direction: dark, technical-minimal "instrument panel" aesthetic —
see [`../docs/FRONTEND_DESIGN.md`](../docs/FRONTEND_DESIGN.md) for the full
design spec (tokens, layout, component patterns, states). This app
implements that spec plus a 3D/scroll-animated landing page (React Three
Fiber + Framer Motion) for the hackathon's UI presentation.

## Stack

- **Next.js 16** (App Router, Turbopack), React 19, TypeScript
- **Tailwind CSS v4** (tokens defined in `app/globals.css` via `@theme`)
- **Framer Motion** — scroll reveals, transitions
- **React Three Fiber + drei** — the landing page's 3D globe
- **MapLibre GL JS** — AOI drawing on the workspace map (free demo tile
  style by default; swap `DEMO_STYLE` in `components/AOIMap.tsx` for a
  provider like MapTiler/Mapbox once you have a key)
- **amazon-cognito-identity-js** — auth against the backend's Cognito User
  Pool (see `../docs/DEPLOYMENT.md` §6 for where the pool/client ids come
  from)
- **Zustand** — small client stores for auth and workspace state

## Run it

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in Cognito ids once you have them
npm run dev
```

Requires the backend running locally (`cd ../backend && uvicorn
app.api.main:app --port 8000`) or `NEXT_PUBLIC_API_URL` pointed at a
deployed API. The landing page and auth screens work without a backend;
`/workspace` needs one to actually run analyses.

Auth is optional on the backend by default (`AUTH_ENABLED=false`), and the
frontend matches it: with **no** `NEXT_PUBLIC_COGNITO_*` ids set, `/workspace`
runs in open **demo mode** (badge in the header, no sign-in, launch buttons go
straight to the workspace). Set both Cognito ids and the sign-in flow and the
`/workspace` route guard turn on (`isAuthConfigured()` in `lib/auth.ts`). To
try it: load the demo field, keep the "Fixtures" data source, and run.

`npm run dev` / `npm run build` first run `scripts/copy-maplibre-worker.mjs`,
which copies MapLibre's web worker into `public/maplibre/` (git-ignored). It is
required: without it the drawn area never appears on the map.

## Structure

```
app/
  page.tsx            landing page (3D hero, scroll-revealed sections)
  login/, signup/, confirm/    Cognito auth screens
  workspace/          the app (map + inspector panel); login-gated only if Cognito is configured
components/
  Globe3D.tsx          landing page hero 3D scene (R3F)
  ScrollReveal.tsx      whileInView animation wrapper
  Navbar.tsx, AuthCard.tsx
  AOIMap.tsx            MapLibre map (satellite basemap) + click-to-draw AOI
  InspectorPanel.tsx    tabs (New/Result | History) + job polling
  QuestionForm.tsx      demo field, question, dates, provider, observation preview
  ResultView.tsx        headline, evidence, how-it-was-produced, curl, JSON
  HistoryList.tsx       recent analyses (GET /v1/analyses)
  CopyButton.tsx
lib/
  api.ts               typed client for the Terra API + friendlyError()
  types.ts             mirrors backend/app/domain/models.py — keep in sync
  auth.ts               Cognito wrapper + isAuthConfigured()/entryHref()
  store.ts, workspaceStore.ts   Zustand stores (auth; AOI/job state)
  demo.ts              the canonical demo AOI/dates (one place, on purpose)
  format.ts, geo.ts    display formatting; AOI area (mirrors the backend's)
scripts/
  copy-maplibre-worker.mjs   predev/prebuild: serve MapLibre's worker from public/
```

## Notes

- `lib/types.ts` is hand-kept in sync with the backend's Pydantic models
  (`backend/app/domain/models.py`) and `docs/openapi.json`. If you change
  the API's request/response shape, update both.
- The workspace map uses the keyless Sentinel-2 cloudless 2020 mosaic from EOX
  so the app shows real imagery with zero API keys. It is **CC BY-NC-SA 4.0**
  (non-commercial) — fine for the hackathon; swap `BASEMAP` in
  `components/AOIMap.tsx` for a commercially licensed provider before any
  commercial launch. Attribution is rendered on the map and listed in the
  root `THIRD_PARTY_NOTICES.md`.
- Live analyses on large drawn areas are slow (see `HANDOFF.md`, item 8); the
  form warns above ~30 km².
- AOI drawing is click-to-add-vertex, double-click to close — intentionally
  minimal for the hackathon timeline; there's no undo/edit-vertex UI yet.
