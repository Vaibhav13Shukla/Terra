import type { AOI } from "./types";

// The canonical demo field: central California farmland. This is the same
// AOI/date pair the backend README and HANDOFF.md document as verified live
// (17-20 low-cloud Sentinel-2 scenes per period), and it is the window the
// deterministic `fixtures` provider has synthetic scenes for (Jul + Aug 2025).
// It lives in one place so the "Use demo field" button, the form defaults and
// the map framing can never drift apart.

export const DEMO_AOI: AOI = {
  type: "Polygon",
  coordinates: [
    [
      [-120.6, 36.95],
      [-120.55, 36.95],
      [-120.55, 37.0],
      [-120.6, 37.0],
      [-120.6, 36.95],
    ],
  ],
};

export const DEMO_DATES = { start: "2025-08-01", end: "2025-08-31" } as const;

export const DEMO_QUESTION = "How has vegetation changed here?";

/** [west, south, east, north] of an AOI's outer ring. */
export function aoiBounds(aoi: AOI): [number, number, number, number] {
  const ring = aoi.coordinates[0];
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return [
    Math.min(...lons),
    Math.min(...lats),
    Math.max(...lons),
    Math.max(...lats),
  ];
}
