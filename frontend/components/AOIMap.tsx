"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AttributionControl,
  Map as MLMap,
  NavigationControl,
  setWorkerUrl,
  type GeoJSONSource,
  type MapMouseEvent,
  type StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useWorkspaceStore } from "@/lib/workspaceStore";
import { DEMO_AOI, aoiBounds } from "@/lib/demo";
import type { AOI } from "@/lib/types";

// MapLibre v6 can't locate its own web worker once Next/Turbopack has bundled
// it (the worker path resolves into /_next/static/chunks/ and 404s), which
// silently disables every GeoJSON layer — including the AOI overlay. Serve the
// worker from /public instead; scripts/copy-maplibre-worker.mjs copies it
// there at predev/prebuild. Must run before the first Map is constructed.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

const SOURCE_ID = "aoi-draft";

// Keyless satellite basemap: the Sentinel-2 cloudless 2020 mosaic from EOX.
// It is the same satellite family Terra analyses, so the field you draw sits
// on imagery you can actually recognise. Licence is CC BY-NC-SA 4.0 —
// fine for this hackathon build, but swap it for a commercially licensed
// basemap (MapTiler / Mapbox) before any commercial launch. Attribution is
// mandatory and rendered by the map's attribution control; the licence is
// also listed in THIRD_PARTY_NOTICES.md.
const BASEMAP: StyleSpecification = {
  version: 8,
  sources: {
    s2cloudless: {
      type: "raster",
      tiles: [
        "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg",
      ],
      tileSize: 256,
      maxzoom: 13,
      attribution:
        '<a href="https://s2maps.eu" target="_blank" rel="noreferrer">Sentinel-2 cloudless</a> by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2020) · <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noreferrer">CC BY-NC-SA 4.0</a>',
    },
  },
  layers: [
    {
      id: "basemap",
      type: "raster",
      source: "s2cloudless",
      // Tone the imagery down a touch so it sits inside the dark UI without
      // resorting to a CSS filter (which would also recolour the AOI).
      paint: { "raster-brightness-max": 0.85, "raster-saturation": -0.1 },
    },
  ],
};

function closedRing(points: [number, number][]): [number, number][] {
  if (points.length < 3) return points;
  const first = points[0];
  const last = points[points.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return points;
  return [...points, first];
}

function buildFeatures(
  aoi: AOI | null,
  draft: [number, number][],
  drawing: boolean
): GeoJSON.Feature[] {
  if (drawing) {
    const features: GeoJSON.Feature[] = draft.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: p },
      properties: {},
    }));
    if (draft.length >= 2) {
      features.push({
        type: "Feature",
        geometry: {
          type: draft.length >= 3 ? "Polygon" : "LineString",
          coordinates: draft.length >= 3 ? [closedRing(draft)] : draft,
        } as GeoJSON.Geometry,
        properties: {},
      });
    }
    return features;
  }
  if (aoi) {
    return [
      {
        type: "Feature",
        geometry: { type: "Polygon", coordinates: aoi.coordinates },
        properties: {},
      },
    ];
  }
  return [];
}

export function AOIMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const pointsRef = useRef<[number, number][]>([]);
  const [mapReady, setMapReady] = useState(false);
  const { aoi, aoiSource, drawing, setAoi, setDrawing } = useWorkspaceStore();

  // Push the current AOI (or the in-progress draft) into the map source.
  // Reads the store directly so it is never stale inside map event handlers.
  const syncSource = useCallback(() => {
    const map = mapRef.current;
    if (!map || !map.getSource(SOURCE_ID)) return;
    const state = useWorkspaceStore.getState();
    (map.getSource(SOURCE_ID) as GeoJSONSource).setData({
      type: "FeatureCollection",
      features: buildFeatures(state.aoi, pointsRef.current, state.drawing),
    });
  }, []);

  // Create the map once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const [w, s, e, n] = aoiBounds(DEMO_AOI);
    const map = new MLMap({
      container: containerRef.current,
      style: BASEMAP,
      center: [(w + e) / 2, (s + n) / 2],
      zoom: 11,
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({}), "top-right");
    map.addControl(new AttributionControl({ compact: true }), "bottom-right");

    // Tile requests are aborted whenever the viewport changes mid-flight, and
    // MapLibre reports those (and any single undecodable tile) through
    // 'error'. With no listener it falls back to console.error, which Next's
    // dev overlay presents as an app crash. Tile errors are non-fatal — the
    // map keeps rendering — so downgrade them to a debug line and leave every
    // other error loud. (Verified: all tiles around the demo field fetch and
    // decode fine, so this is abort noise, not a bad tile.)
    map.on("error", (e) => {
      const { sourceId } = e as unknown as { sourceId?: string };
      if (sourceId === "s2cloudless") {
        console.debug("[map] basemap tile error:", e.error?.message);
        return;
      }
      console.error(e.error);
    });

    // 'style.load' (not 'load'): 'load' waits for every initial tile to
    // finish, so one stalled/aborted tile could delay it and the AOI overlay
    // would never get its layers. The overlay only needs the style.
    map.on("style.load", () => {
      map.addSource(SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: `${SOURCE_ID}-fill`,
        type: "fill",
        source: SOURCE_ID,
        filter: ["==", "$type", "Polygon"],
        paint: { "fill-color": "#22d3aa", "fill-opacity": 0.18 },
      });
      map.addLayer({
        id: `${SOURCE_ID}-line`,
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#52d9c4", "line-width": 2 },
      });
      map.addLayer({
        id: `${SOURCE_ID}-points`,
        type: "circle",
        source: SOURCE_ID,
        filter: ["==", "$type", "Point"],
        paint: {
          "circle-radius": 4,
          "circle-color": "#52d9c4",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#07080a",
        },
      });
      setMapReady(true);
    });

    return () => {
      map.remove();
      mapRef.current = null;
      setMapReady(false);
    };
  }, []);

  // Keep the drawn/loaded AOI on the map whenever the store changes — this is
  // what makes a programmatically-loaded demo field (and "New analysis"
  // resets) show up, not just hand-drawn polygons.
  useEffect(() => {
    if (mapReady) syncSource();
  }, [mapReady, aoi, drawing, syncSource]);

  // Frame a demo field when it is loaded (a hand-drawn one is already in view).
  useEffect(() => {
    if (!mapReady || !aoi || aoiSource !== "demo") return;
    const [w, s, e, n] = aoiBounds(aoi);
    mapRef.current?.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: 90, duration: 900, maxZoom: 13 }
    );
  }, [mapReady, aoi, aoiSource]);

  const finishDrawing = useCallback(() => {
    if (pointsRef.current.length >= 3) {
      setAoi(
        { type: "Polygon", coordinates: [closedRing(pointsRef.current)] },
        "drawn"
      );
    }
    setDrawing(false);
  }, [setAoi, setDrawing]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;

    function handleClick(e: MapMouseEvent) {
      if (!drawing) return;
      const next: [number, number] = [e.lngLat.lng, e.lngLat.lat];
      const last = pointsRef.current[pointsRef.current.length - 1];
      // A double-click fires two click events at the same spot before the
      // dblclick; skip the duplicate so it doesn't add a zero-length edge.
      if (last && last[0] === next[0] && last[1] === next[1]) return;
      pointsRef.current.push(next);
      syncSource();
    }

    function handleDblClick(e: MapMouseEvent) {
      if (!drawing) return;
      e.preventDefault();
      finishDrawing();
    }

    map.on("click", handleClick);
    map.on("dblclick", handleDblClick);
    return () => {
      map.off("click", handleClick);
      map.off("dblclick", handleDblClick);
    };
  }, [drawing, finishDrawing, mapReady, syncSource]);

  function startDrawing() {
    pointsRef.current = [];
    setAoi(null);
    setDrawing(true);
  }

  function clearAoi() {
    pointsRef.current = [];
    setAoi(null);
    setDrawing(false);
  }

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="map-canvas h-full w-full" />
      <div className="glass-panel absolute left-4 top-4 flex gap-2 p-2">
        {!drawing ? (
          <button
            onClick={startDrawing}
            className="rounded-[var(--radius-sm)] px-3 py-1.5 text-xs font-medium text-text-primary transition hover:bg-inset"
          >
            Draw area
          </button>
        ) : (
          <button
            onClick={finishDrawing}
            className="rounded-[var(--radius-sm)] bg-accent px-3 py-1.5 text-xs font-medium text-canvas"
          >
            Finish (or double-click)
          </button>
        )}
        <button
          onClick={clearAoi}
          className="rounded-[var(--radius-sm)] px-3 py-1.5 text-xs text-text-secondary transition hover:bg-inset hover:text-text-primary"
        >
          Clear
        </button>
      </div>
      {drawing && (
        <p className="glass-panel pointer-events-none absolute bottom-4 left-4 px-3 py-2 text-xs text-text-secondary">
          Click to add corners &middot; double-click to finish (min. 3)
        </p>
      )}
    </div>
  );
}
