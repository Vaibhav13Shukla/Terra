"use client";

import { useEffect, useRef, useState } from "react";
import { friendlyError, terraApi } from "@/lib/api";
import { DEMO_AOI, DEMO_DATES, DEMO_QUESTION, aoiBounds } from "@/lib/demo";
import { isFixtureProvider } from "@/lib/format";
import { aoiAreaKm2, formatKm2 } from "@/lib/geo";
import { useWorkspaceStore } from "@/lib/workspaceStore";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

// Measured against the real backend on live Sentinel-2 (synchronous mode):
// the ~25 km² demo field finishes in roughly 20–30 s, while a hand-drawn
// ~47 km² area took ~200 s (and a second concurrent request timed out).
// Latency grows much faster than area, and a deployed API Gateway cuts
// synchronous requests off at 29 s — so warn well before that point rather
// than let someone wait minutes on a request that may never finish.
const LARGE_LIVE_AREA_KM2 = 30;
// After this long, say plainly that a live run is slower than the docs suggest.
const SLOW_NOTICE_SECONDS = 45;

const SUGGESTIONS = [
  DEMO_QUESTION,
  "What is the vegetation index here?",
] as const;

type Preview =
  | { key: string; ok: true; used: number; rejected: number }
  | { key: string; ok: false; message: string };

export function QuestionForm() {
  const { aoi, setAoi, setJob, setPolling, setError } = useWorkspaceStore();
  const [question, setQuestion] = useState<string>(DEMO_QUESTION);
  const [provider, setProvider] = useState("fixtures");
  const [startDate, setStartDate] = useState<string>(DEMO_DATES.start);
  const [endDate, setEndDate] = useState<string>(DEMO_DATES.end);
  const [submitting, setSubmitting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(0);

  const datesValid = Boolean(startDate && endDate && startDate <= endDate);

  // --- Observations preview (real /v1/scenes call, debounced) -------------
  // Keyed by everything that affects the answer, so a stale response for an
  // old AOI/date/provider can never be shown against the current inputs.
  const previewKey =
    aoi && datesValid
      ? `${provider}|${startDate}|${endDate}|${JSON.stringify(aoi.coordinates)}`
      : null;
  const [preview, setPreview] = useState<Preview | null>(null);

  useEffect(() => {
    if (!previewKey || !aoi) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const [west, south, east, north] = aoiBounds(aoi);
        const res = await terraApi.scenes({
          min_lon: west,
          min_lat: south,
          max_lon: east,
          max_lat: north,
          start_date: startDate,
          end_date: endDate,
          provider,
        });
        if (!cancelled) {
          setPreview({
            key: previewKey,
            ok: true,
            used: res.scenes_used,
            rejected: res.scenes_rejected,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setPreview({
            key: previewKey,
            ok: false,
            message: friendlyError(err),
          });
        }
      }
    }, 450);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [previewKey, aoi, startDate, endDate, provider]);

  const currentPreview = preview && preview.key === previewKey ? preview : null;

  // --- Elapsed timer while a request is in flight --------------------------
  useEffect(() => {
    if (!submitting) return;
    const id = setInterval(
      () => setElapsed(Math.round((Date.now() - startedAt.current) / 1000)),
      1000
    );
    return () => clearInterval(id);
  }, [submitting]);

  function loadDemoField() {
    setAoi(DEMO_AOI, "demo");
    setStartDate(DEMO_DATES.start);
    setEndDate(DEMO_DATES.end);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!aoi || !datesValid) return;
    setSubmitting(true);
    setElapsed(0);
    startedAt.current = Date.now();
    setError(null);
    try {
      const job = await terraApi.createAnalysis({
        aoi,
        start_date: startDate,
        end_date: endDate,
        provider,
        question,
      });
      setJob(job);
      if (!TERMINAL_STATUSES.has(job.status)) setPolling(true);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setSubmitting(false);
    }
  }

  const live = !isFixtureProvider(provider);
  const areaKm2 = aoi ? aoiAreaKm2(aoi) : 0;
  const largeLiveArea = live && areaKm2 > LARGE_LIVE_AREA_KM2;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {!aoi && (
        <div className="rounded-[var(--radius-sm)] border border-border bg-inset p-3">
          <p className="text-sm text-text-secondary">
            Draw an area on the map, or start with the demo field.
          </p>
          <button
            type="button"
            onClick={loadDemoField}
            className="mt-2 rounded-[var(--radius-sm)] border border-accent/50 px-3 py-1.5 text-xs font-medium text-accent transition hover:bg-accent/10"
          >
            Use demo field (central California)
          </button>
        </div>
      )}

      <label className="block text-sm">
        <span className="mb-1.5 block text-text-secondary">Question</span>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="w-full rounded-[var(--radius-sm)] border border-border bg-inset px-3 py-2.5 text-sm outline-none focus:border-border-strong"
          placeholder={DEMO_QUESTION}
        />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setQuestion(s)}
              className="rounded-full border border-border px-2.5 py-1 text-[11px] text-text-tertiary transition hover:border-border-strong hover:text-text-secondary"
            >
              {s}
            </button>
          ))}
        </div>
      </label>

      <div>
        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="mb-1.5 block text-text-secondary">From</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="text-mono-num w-full rounded-[var(--radius-sm)] border border-border bg-inset px-3 py-2 text-xs outline-none focus:border-border-strong"
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block text-text-secondary">To</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="text-mono-num w-full rounded-[var(--radius-sm)] border border-border bg-inset px-3 py-2 text-xs outline-none focus:border-border-strong"
            />
          </label>
        </div>
        {datesValid ? (
          <p className="mt-2 text-[11px] leading-relaxed text-text-tertiary">
            Questions about change compare this period with the equal-length
            period just before it.
          </p>
        ) : (
          <p className="mt-2 text-[11px] text-negative">
            The start date must be on or before the end date.
          </p>
        )}
      </div>

      <label className="block text-sm">
        <span className="mb-1.5 block text-text-secondary">Data source</span>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="w-full rounded-[var(--radius-sm)] border border-border bg-inset px-3 py-2.5 text-sm outline-none focus:border-border-strong"
        >
          <option value="fixtures">Fixtures — synthetic demo data</option>
          <option value="sentinel-2-l2a">Sentinel-2 L2A — live imagery</option>
        </select>
        <p className="mt-2 text-[11px] leading-relaxed text-text-tertiary">
          {live
            ? "Real Sentinel-2 from AWS Open Data. Reads only your field's pixels — roughly 20–30 s for a field-sized area (~25 km²), longer for larger ones."
            : "Deterministic synthetic scenes (Jul–Aug 2025 only) for a reproducible walkthrough — not real imagery."}
        </p>
      </label>

      {aoi && datesValid && (
        <div
          className="space-y-1.5 rounded-[var(--radius-sm)] border border-border px-3 py-2 text-xs"
          aria-live="polite"
        >
          <p className="text-text-tertiary">
            Area{" "}
            <span className="text-mono-num text-text-secondary">
              {formatKm2(areaKm2)}
            </span>
          </p>
          {largeLiveArea && (
            <p className="text-warning">
              Large for live imagery — areas over ~{LARGE_LIVE_AREA_KM2} km² can
              take several minutes and may time out. A smaller field is much
              faster.
            </p>
          )}
          {!currentPreview && (
            <p className="text-text-tertiary">Checking available observations…</p>
          )}
          {currentPreview?.ok && currentPreview.used > 0 && (
            <p className="text-text-secondary">
              <span className="text-mono-num text-positive">
                {currentPreview.used}
              </span>{" "}
              usable observation{currentPreview.used === 1 ? "" : "s"} in this
              period
              {currentPreview.rejected > 0 &&
                ` · ${currentPreview.rejected} rejected (cloud/quality)`}
            </p>
          )}
          {currentPreview?.ok && currentPreview.used === 0 && (
            <p className="text-warning">
              No usable observations in this period
              {isFixtureProvider(provider)
                ? " — fixtures only cover Jul–Aug 2025."
                : " — try wider dates or a different area."}
            </p>
          )}
          {currentPreview && !currentPreview.ok && (
            <p className="text-warning">{currentPreview.message}</p>
          )}
        </div>
      )}

      <button
        type="submit"
        disabled={!aoi || !datesValid || submitting}
        className="w-full rounded-[var(--radius-sm)] border border-text-primary bg-text-primary py-2.5 text-sm font-medium text-canvas transition hover:opacity-90 disabled:opacity-40"
      >
        {!aoi
          ? "Draw an area on the map first"
          : submitting
            ? `Running analysis… ${elapsed}s`
            : "Run analysis"}
      </button>
      {submitting && (
        <div className="space-y-1.5 text-center text-[11px] text-text-tertiary">
          <p>
            Searching scenes · reading your field&apos;s pixels · computing NDVI
          </p>
          {live && elapsed >= SLOW_NOTICE_SECONDS && (
            <p className="text-warning">
              Taking longer than usual — live imagery is network-bound, and
              larger areas read more of it. It&apos;s still running.
            </p>
          )}
        </div>
      )}
    </form>
  );
}
