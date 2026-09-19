import type { AOI } from "./types";

const KM_PER_DEG = 111.32;

/**
 * Approximate area of an AOI in km², using the same equirectangular scaling
 * the backend uses for its own AOI size budget (backend/app/services/
 * geometry.py `_approx_area_km2`: polygon area in deg², scaled by cos(latitude
 * of the centroid) and 111.32² km²/deg²). Matching it means the number shown
 * here agrees with the limit the API will enforce. This is for a size hint,
 * not for scientific area reporting.
 */
export function aoiAreaKm2(aoi: AOI): number {
  const ring = aoi.coordinates[0];
  if (ring.length < 4) return 0;

  // Shoelace formula in degrees.
  let twiceArea = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    twiceArea += x1 * y2 - x2 * y1;
  }
  const deg2 = Math.abs(twiceArea) / 2;

  const centroidLat =
    ring.slice(0, -1).reduce((sum, p) => sum + p[1], 0) / (ring.length - 1);
  return deg2 * Math.cos((centroidLat * Math.PI) / 180) * KM_PER_DEG ** 2;
}

/** "25.4 km²" / "180 km²" — one decimal below 100, none above. */
export function formatKm2(km2: number): string {
  return `${km2 < 100 ? km2.toFixed(1) : Math.round(km2)} km²`;
}
