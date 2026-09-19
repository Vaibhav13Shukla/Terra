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

Auth is optional on the backend by default (`AUTH_ENABLED=false`) — you can
exercise `/workspace`'s analysis flow by logging in only once the backend
has `AUTH_ENABLED=true` and a Cognito pool configured. Until then, the
client-side route guard on `/workspace` still requires a session token, so
sign up/log in against a real deployed Cognito pool to reach it.

## Structure

```
app/
  page.tsx            landing page (3D hero, scroll-revealed sections)
  login/, signup/, confirm/    Cognito auth screens
  workspace/          the authenticated app (map + inspector panel)
components/
  Globe3D.tsx          landing page hero 3D scene (R3F)
  ScrollReveal.tsx      whileInView animation wrapper
  Navbar.tsx, AuthCard.tsx
  AOIMap.tsx            MapLibre map + click-to-draw AOI polygon
  InspectorPanel.tsx    question form + result/evidence/status display
lib/
  api.ts               typed client for the Terra API
  types.ts             mirrors backend/app/domain/models.py — keep in sync
  auth.ts               Cognito wrapper (signup/confirm/login/tokens)
  store.ts, workspaceStore.ts   Zustand stores
```

## Notes

- `lib/types.ts` is hand-kept in sync with the backend's Pydantic models
  (`backend/app/domain/models.py`) and `docs/openapi.json`. If you change
  the API's request/response shape, update both.
- The workspace map uses MapLibre's free `demotiles.maplibre.org` style so
  the app works with zero API keys out of the box. It's a minimal
  basemap — swap in a proper vector/dark tile provider before a public
  launch.
- AOI drawing is click-to-add-vertex, double-click to close — intentionally
  minimal for the hackathon timeline; there's no undo/edit-vertex UI yet.
