"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  Map as MLMap,
  NavigationControl,
  type GeoJSONSource,
  type MapMouseEvent,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useWorkspaceStore } from "@/lib/workspaceStore";
import type { AOI } from "@/lib/types";

const SOURCE_ID = "aoi-draft";
const DEMO_STYLE = "https://demotiles.maplibre.org/style.json";

function closedRing(points: [number, number][]): [number, number][] {
  if (points.length < 3) return points;
  const first = points[0];
  const last = points[points.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return points;
  return [...points, first];
}

export function AOIMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const pointsRef = useRef<[number, number][]>([]);
  const { drawing, setAoi, setDrawing } = useWorkspaceStore();

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new MLMap({
      container: containerRef.current,
      style: DEMO_STYLE,
      center: [-120.575, 36.975],
      zoom: 10,
      attributionControl: false,
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({}), "top-right");

    map.on("load", () => {
      map.addSource(SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: `${SOURCE_ID}-fill`,
        type: "fill",
        source: SOURCE_ID,
        filter: ["==", "$type", "Polygon"],
        paint: { "fill-color": "#22d3aa", "fill-opacity": 0.15 },
      });
      map.addLayer({
        id: `${SOURCE_ID}-line`,
        type: "line",
        source: SOURCE_ID,
        paint: { "line-color": "#22d3aa", "line-width": 2 },
      });
      map.addLayer({
        id: `${SOURCE_ID}-points`,
        type: "circle",
        source: SOURCE_ID,
        filter: ["==", "$type", "Point"],
        paint: {
          "circle-radius": 4,
          "circle-color": "#22d3aa",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#07080a",
        },
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  function renderDraft() {
    const map = mapRef.current;
    if (!map || !map.getSource(SOURCE_ID)) return;
    const pts = pointsRef.current;
    const features: GeoJSON.Feature[] = pts.map((p) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: p },
      properties: {},
    }));
    if (pts.length >= 2) {
      features.push({
        type: "Feature",
        geometry: {
          type: pts.length >= 3 ? "Polygon" : "LineString",
          coordinates: pts.length >= 3 ? [closedRing(pts)] : pts,
        } as GeoJSON.Geometry,
        properties: {},
      });
    }
    (map.getSource(SOURCE_ID) as GeoJSONSource).setData({
      type: "FeatureCollection",
      features,
    });
  }

  const finishDrawing = useCallback(() => {
    if (pointsRef.current.length >= 3) {
      const ring = closedRing(pointsRef.current);
      const aoi: AOI = { type: "Polygon", coordinates: [ring] };
      setAoi(aoi);
    }
    setDrawing(false);
  }, [setAoi, setDrawing]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    function handleClick(e: MapMouseEvent) {
      if (!drawing) return;
      pointsRef.current.push([e.lngLat.lng, e.lngLat.lat]);
      renderDraft();
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
  }, [drawing, finishDrawing]);

  function startDrawing() {
    pointsRef.current = [];
    setAoi(null);
    setDrawing(true);
    renderDraft();
  }

  function clearAoi() {
    pointsRef.current = [];
    setAoi(null);
    setDrawing(false);
    renderDraft();
  }

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="map-canvas h-full w-full"
      />
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
    </div>
  );
}
