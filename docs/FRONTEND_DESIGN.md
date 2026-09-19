# Terra — Frontend Design Direction

For the frontend teammate. This is a design spec, not implementation — the
frontend is built separately (see root `CLAUDE.md`). Written from general
product-design knowledge, not a live browse of any specific reference site
(network access to styles.refero.design was blocked in the session that
drafted this — see git history if you want the detail).

## Why this direction

Terra's whole pitch is **scientific honesty**: a number is worthless without
its evidence (scenes used/rejected, cloud cover, valid-pixel ratio,
limitations). That rules out a "consumer app" aesthetic — bright gradients,
big rounded cards, playful illustration — because it visually undersells a
tool that's supposed to read as rigorous. It also rules out a dense
enterprise-BI look (crowded toolbars, heavy borders everywhere) because the
actual product surface is small: draw an area, ask a question, get one
number with its trail.

The right reference class is **technical-minimal product UI** — the
Linear / Vercel / Stripe Dashboard / Mapbox Studio family. Common traits
worth copying directly:

- Dark-mode-first (or true dark/light parity), near-black/near-white
  backgrounds rather than gray-500 "cards on gray-100," minimal chrome.
- Monospace (or tabular-lining numerals) for anything measured — metrics,
  percentages, dates, ids — proportional sans for everything else. This one
  choice alone reads as "instrument," not "app."
- Restrained color: near-grayscale UI, color spent only on semantic meaning
  (a metric's direction, a status badge, a warning). Never decorative color.
- Borders and 1px dividers instead of drop shadows for structure; shadows
  reserved for actual overlays (modals, popovers, the command palette).
- A persistent two-pane shell: primary content (the map) + a right-hand
  inspector panel, closer to Mapbox Studio / Linear's issue detail panel
  than to a traditional dashboard-with-sidebar-nav layout — because for
  Terra the map IS the app, and the panel is where evidence lives.

## Color tokens

Dark is the default theme (matches the "instrument panel" read); light is a
straight token swap, not a redesign.

```
--bg              #0A0B0D   (near-black, not pure #000 — avoids OLED smear)
--bg-elevated     #121316   (panels, cards)
--bg-inset        #1A1C20   (input fields, code/mono blocks)
--border          #26282D
--border-strong   #3A3D44
--text-primary    #F2F3F5
--text-secondary  #A0A4AC
--text-tertiary   #6B6F78
--accent          #5B8DEF   (links, focus rings, primary actions — a
                             restrained blue, not a brand-loud color)
--positive        #3DBD7D   (NDVI increase / "success" status)
--negative        #E5604B   (NDVI decrease / "failed" status)
--warning         #E0A94A   (low confidence, single-scene result, cloud cover)
--scale-mono      "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace
```

Light theme: `--bg:#FFFFFF`, `--bg-elevated:#F7F7F8`, `--bg-inset:#F0F1F3`,
`--border:#E4E5E8`, `--text-primary:#111214`, `--text-secondary:#5B5F68`,
keep `--accent`/`--positive`/`--negative`/`--warning` identical (semantic
colors should not shift between themes — a judge switching themes mid-demo
shouldn't see NDVI-down turn a different red).

## Typography

- UI text: Inter or system-ui, 14px base, 1.5 line-height.
- Headings: same family, weight 600, tight tracking (-0.01em), no display
  font — this product doesn't need personality typography, it needs to read
  as precise.
- Numbers/metrics/dates/ids: `--scale-mono` throughout, including inside
  otherwise-sans components (a metric card's big number, a job id, a
  timestamp, "cloud_threshold: 20%"). Use tabular-nums even in the sans
  font for anything that appears in a list (scene counts, percentages) so
  columns align.
- Scale: 12 / 14 / 16 / 20 / 28 / 40px. The big NDVI percentage-change
  number is the one place to go to 40px+ mono — it's the product's single
  most important pixel.

## Spacing, radius, elevation

- 4px base unit; use 8/12/16/24/32/48 in practice.
- Radius: 6px for buttons/inputs, 10px for panels/cards. Nothing pill-shaped
  except status badges.
- Elevation: none for static layout (borders do the work); a soft shadow
  only for the command palette / modals / dropdown menus, e.g.
  `0 8px 24px rgba(0,0,0,0.35)` on dark.

## Layout: app shell

```
┌──────────────────────────────────────────────────────────────┐
│  Terra    [provider: sentinel-2-l2a ▾]        [user ▾ / login]│  ← 48px top bar
├──────────────────────────────────┬───────────────────────────┤
│                                    │  INSPECTOR PANEL (380px)  │
│                                    │  ─────────────────────    │
│                                    │  Question / request        │
│         MAP CANVAS                │  ─────────────────────    │
│      (AOI draw + scene            │  Result                    │
│       footprint overlay)          │    NDVI change: -18.2%     │
│                                    │    (big mono number,       │
│                                    │     colored by direction)  │
│                                    │  ─────────────────────    │
│                                    │  Data quality               │
│                                    │    8 used · 32 rejected     │
│                                    │    valid pixels: 94%        │
│                                    │  ─────────────────────    │
│                                    │  Evidence (scenes list,     │
│                                    │  expandable, cloud % per    │
│                                    │  scene, rejection reasons)  │
│                                    │  ─────────────────────    │
│                                    │  Limitations (always shown, │
│                                    │  never collapsed by default)│
└────────────────────────────────────┴───────────────────────────┘
```

No left sidebar nav — there's nothing to navigate to yet beyond "new
analysis" / "history," which fit in the top bar as a dropdown. Don't build
enterprise-dashboard chrome the product doesn't need.

## Key components

**AOI drawing** — a minimal floating toolbar over the map (draw polygon /
clear), not a docked toolbar. Selected AOI renders as a translucent accent
fill with a solid accent border; candidate/used scene footprints render as
thin dashed outlines in `--text-tertiary`, switching to `--positive`/
`--negative`-tinted outlines only once a result exists (used vs. rejected).

**Question bar** — one input, natural language or structured toggle
(matches the API's `question` vs `analysis` fields). Keep it single-line
with an expand affordance, not a chat window — Terra is one-shot analysis,
not a conversation.

**Metric display** — the NDVI number is the hero: big mono number, a small
sparkline-free "current → comparison" pair beneath it in smaller mono, and
a colored delta chip (`--positive`/`--negative`). Never render a naked
percentage without its `current_value`/`comparison_value` context — matches
the backend's own "scientific honesty" rule (report "%, decreased", never a
qualitative claim).

**Data quality panel** — a fixed-position summary, not buried in a
collapsed section: `scenes_used`, `scenes_rejected`, `cloud_threshold`,
`valid_pixel_ratio` as a compact stat row (mono numbers, sans labels).

**Evidence / scenes list** — expandable list, each row: scene id (mono,
truncated), date, cloud % (colored if it drove rejection), and — only for
rejected scenes — the `rejection_reason` string verbatim from the API. Don't
paraphrase it; it's already written to be shown to a user.

**Limitations callout** — a persistent, low-alarm banner (not a red error
box — this is a stated scientific caveat, not a failure) using `--warning`
at low opacity, always visible when `limitations` is non-empty, never
default-collapsed.

**Job status** — badges for `created` / `discovering` / `processing` /
`analyzing` / `completed` / `failed`, pill-shaped (the one place pills are
OK), neutral gray for in-progress states, `--positive`/`--negative` only
for the terminal states. Poll `GET /v1/analyses/{id}` on an interval while
non-terminal; this matters more once `TERRA_PROCESSING_MODE=async` is in
use (jobs return immediately in `created` status).

**Auth** — Cognito-backed (see `docs/DEPLOYMENT.md` for the pool/client
ids). A single login/signup surface is enough; don't build a full account
settings area for the hackathon. Show the signed-in state as a simple
avatar/email menu in the top bar, not a persistent sidebar.

## States to design explicitly (don't skip these — judges probe them)

- **Loading/polling**: skeleton for the inspector panel, not a full-page
  spinner — the map should stay interactive.
- **No usable data** (`status: "failed"` with a message, not an HTTP
  error): render the API's own message directly, plus the scenes that
  were found and why they were rejected — this is a legitimate, informative
  outcome per the backend's design, not an error state.
- **Unsupported question** (422): show `intent.reason` verbatim, invite a
  rephrase — don't design this as a hard error page.
- **Single-scene / low-confidence result**: surface the
  `limitations` entry about limited confidence prominently, same treatment
  as the general limitations callout.
- **Auth required** (401, once `AUTH_ENABLED=true`): redirect to login,
  preserve the pending AOI/question so it isn't lost.

## Accessibility & responsiveness

- All semantic colors (`--positive`/`--negative`/`--warning`) must pair with
  a non-color signal (icon or label) — don't rely on red/green alone for the
  NDVI direction.
- Keyboard-operable AOI drawing is out of scope for a hackathon timeline;
  document it as a known gap rather than skipping silently.
- Below ~900px width, collapse to a single column: map first, inspector
  panel becomes a bottom sheet/drawer triggered after a result exists.
