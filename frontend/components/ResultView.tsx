"use client";

import { useState, type ReactNode } from "react";
import { API_URL } from "@/lib/api";
import { isAuthConfigured } from "@/lib/auth";
import {
  analysisLabel,
  formatPercent,
  formatRange,
  hasNoData,
  isFixtureProvider,
  isRunning,
  providerLabel,
  statusLabel,
  stripLimitations,
} from "@/lib/format";
import type { AnalysisJob } from "@/lib/types";
import { CopyButton } from "./CopyButton";

function StatusBadge({
  status,
  noData,
}: {
  status: AnalysisJob["status"];
  noData: boolean;
}) {
  // A job can finish ("completed") while the analysis itself found nothing to
  // compute — that must not read as a green success next to "No result".
  const showNoData = noData && status === "completed";
  const color = showNoData
    ? "text-warning border-warning/40"
    : status === "completed"
      ? "text-positive border-positive/40"
      : status === "failed"
        ? "text-negative border-negative/40"
        : "text-text-secondary border-border-strong";
  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${color}`}
    >
      {showNoData ? "no data" : statusLabel(status)}
    </span>
  );
}

function Disclosure({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-border pt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between text-sm font-medium text-text-primary"
      >
        <span>{title}</span>
        <span className="flex items-center gap-2 text-text-tertiary">
          {aside}
          <span aria-hidden>{open ? "−" : "+"}</span>
        </span>
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  );
}

/** The exact request that produced this job, as a copy-pasteable curl call. */
function buildCurl(job: AnalysisJob): string {
  const r = job.request;
  const body = {
    aoi: r.aoi,
    start_date: r.date_range.start,
    end_date: r.date_range.end,
    ...(r.comparison_range
      ? {
          comparison_start_date: r.comparison_range.start,
          comparison_end_date: r.comparison_range.end,
        }
      : {}),
    analysis: r.analysis_type,
    cloud_threshold: r.cloud_threshold,
    provider: r.provider,
  };
  const lines = [
    `curl -X POST "${API_URL}/v1/analyses"`,
    `  -H "Content-Type: application/json"`,
  ];
  if (isAuthConfigured()) {
    lines.push(`  -H "Authorization: Bearer $TERRA_ID_TOKEN"`);
  }
  lines.push(`  -d '${JSON.stringify(body)}'`);
  return lines.join(" \\\n");
}

export function ResultView({
  job,
  polling = false,
}: {
  job: AnalysisJob;
  /** Whether the workspace is currently polling this job for updates. */
  polling?: boolean;
}) {
  const result = job.result;
  const metric = result?.metric;
  const change = metric?.percentage_change;
  const fixture = isFixtureProvider(job.request.provider);
  const noResult = hasNoData(job);

  const scenes = result?.evidence?.scenes ?? [];
  const usedScenes = scenes.filter((s) => s.selected);
  const rejectedScenes = scenes.filter((s) => !s.selected);
  const steps = result?.evidence?.processing_steps ?? [];
  const explanation = result?.explanation
    ? stripLimitations(result.explanation, result.limitations ?? [])
    : "";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm text-text-primary">
            {analysisLabel(job.request.analysis_type)}
          </p>
          <p className="text-mono-num text-xs text-text-tertiary">
            {job.job_id.slice(0, 8)}
          </p>
        </div>
        <StatusBadge status={job.status} noData={noResult} />
      </div>

      {fixture ? (
        <div className="rounded-[var(--radius-sm)] border border-warning/30 bg-warning/10 p-3 text-xs leading-relaxed text-warning">
          <span className="font-medium">Fixture data.</span> This result comes
          from synthetic, deterministic scenes built for reproducible demos —
          not live satellite imagery. Switch the provider to Sentinel-2 to
          analyse real observations.
        </div>
      ) : (
        <p className="text-xs text-text-tertiary">
          Source: {providerLabel(job.request.provider)} · AWS Open Data
        </p>
      )}

      {isRunning(job) ? (
        <div
          role="status"
          className="rounded-[var(--radius-sm)] border border-border-strong bg-inset p-4"
        >
          <p className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <span
              aria-hidden
              className="inline-block h-2 w-2 animate-pulse rounded-full bg-text-secondary"
            />
            {job.status === "created"
              ? "Queued — waiting for a worker"
              : "Analysing Sentinel-2 scenes…"}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            {polling
              ? "This page checks for the result every few seconds. Live analyses can take from about half a minute to several minutes, depending on the size of the area."
              : "This page is no longer checking for updates. Reopen this analysis from History to see whether it has finished."}
          </p>
        </div>
      ) : noResult ? (
        <div className="rounded-[var(--radius-sm)] border border-border-strong bg-inset p-4">
          <p className="text-sm font-medium text-text-primary">
            No result for this request
          </p>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            {result?.message ?? job.error ?? "The analysis could not be completed."}
          </p>
          <p className="mt-3 text-xs text-text-tertiary">
            Terra reports missing data as missing — it never turns an empty
            search into an answer.
          </p>
        </div>
      ) : (
        metric && (
          <div>
            <p className="text-xs uppercase tracking-wide text-text-tertiary">
              {metric.name}
              {change !== null && change !== undefined ? " change" : ""}
            </p>
            <p
              className={`text-mono-num mt-1 text-4xl font-medium ${
                change === null || change === undefined
                  ? "text-text-primary"
                  : change < 0
                    ? "text-negative"
                    : "text-positive"
              }`}
            >
              {change !== null && change !== undefined
                ? formatPercent(change)
                : metric.current_value.toFixed(3)}
            </p>
            {metric.comparison_value !== null &&
              metric.comparison_value !== undefined && (
                <p className="text-mono-num mt-1 text-xs text-text-secondary">
                  {metric.comparison_value.toFixed(3)} &rarr;{" "}
                  {metric.current_value.toFixed(3)} mean NDVI
                </p>
              )}
            <div className="mt-3 space-y-0.5 text-xs text-text-tertiary">
              <p>Current: {formatRange(job.request.date_range)}</p>
              {job.request.comparison_range && (
                <p>Compared with: {formatRange(job.request.comparison_range)}</p>
              )}
            </div>
          </div>
        )
      )}

      {!noResult && explanation && (
        <p className="border-t border-border pt-4 text-sm leading-relaxed text-text-secondary">
          {explanation}
        </p>
      )}

      {result?.data_quality && (
        <div className="grid grid-cols-4 gap-3 border-t border-border pt-4 text-sm">
          <div>
            <p className="text-mono-num text-text-primary">
              {result.data_quality.scenes_used}
            </p>
            <p className="text-xs text-text-tertiary">used</p>
          </div>
          <div>
            <p className="text-mono-num text-text-primary">
              {result.data_quality.scenes_rejected}
            </p>
            <p className="text-xs text-text-tertiary">rejected</p>
          </div>
          <div>
            <p className="text-mono-num text-text-primary">
              {result.data_quality.valid_pixel_ratio !== null &&
              result.data_quality.valid_pixel_ratio !== undefined
                ? `${Math.round(result.data_quality.valid_pixel_ratio * 100)}%`
                : "—"}
            </p>
            <p className="text-xs text-text-tertiary">valid px</p>
          </div>
          <div>
            <p className="text-mono-num text-text-primary">
              &lt;{result.data_quality.cloud_threshold}%
            </p>
            <p className="text-xs text-text-tertiary">cloud cap</p>
          </div>
        </div>
      )}

      {result?.limitations && result.limitations.length > 0 && (
        <div className="rounded-[var(--radius-sm)] border border-warning/30 bg-warning/10 p-3 text-xs leading-relaxed text-warning">
          {result.limitations.map((l, i) => (
            <p key={i} className={i > 0 ? "mt-2" : ""}>
              {l}
            </p>
          ))}
        </div>
      )}

      {(result?.evidence?.formula || steps.length > 0) && (
        <Disclosure title="How this result was produced">
          {result?.evidence?.formula && (
            <div className="panel px-3 py-2">
              <p className="text-mono-num text-xs text-text-primary">
                {result.evidence.formula}
              </p>
              {result.evidence.bands_used.length > 0 && (
                <p className="mt-1 text-xs text-text-tertiary">
                  Bands: {result.evidence.bands_used.join(", ")}
                </p>
              )}
            </div>
          )}
          {steps.length > 0 && (
            <ol className="mt-3 space-y-2">
              {steps.map((s, i) => (
                <li key={`${s.name}-${i}`} className="text-xs">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-mono-num text-text-primary">
                      {s.name}
                    </span>
                    {s.duration_ms !== null && s.duration_ms !== undefined && (
                      <span className="text-mono-num shrink-0 text-text-tertiary">
                        {s.duration_ms < 1000
                          ? `${Math.round(s.duration_ms)} ms`
                          : `${(s.duration_ms / 1000).toFixed(1)} s`}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-text-tertiary">{s.detail}</p>
                </li>
              ))}
            </ol>
          )}
        </Disclosure>
      )}

      {scenes.length > 0 && (
        <Disclosure
          title={`Evidence (${usedScenes.length} used · ${rejectedScenes.length} rejected)`}
        >
          <ul className="space-y-2">
            {[...usedScenes, ...rejectedScenes].map((s) => (
              <li
                key={s.id}
                className="panel flex items-start justify-between gap-3 px-3 py-2 text-xs"
              >
                <div className="min-w-0">
                  <p
                    className="text-mono-num truncate text-text-primary"
                    title={s.id}
                  >
                    {s.id}
                  </p>
                  <p className="text-text-tertiary">
                    {new Date(s.datetime).toLocaleDateString("en-GB", {
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                      timeZone: "UTC",
                    })}
                    {s.cloud_cover !== null &&
                      ` · ${s.cloud_cover.toFixed(1)}% cloud`}
                  </p>
                  {s.rejection_reason && (
                    <p className="mt-1 text-warning">{s.rejection_reason}</p>
                  )}
                </div>
                <span
                  className={`text-mono-num shrink-0 ${s.selected ? "text-positive" : "text-text-tertiary"}`}
                >
                  {s.selected ? "used" : "rejected"}
                </span>
              </li>
            ))}
          </ul>
        </Disclosure>
      )}

      <Disclosure title="Use via API" aside={<span className="text-[11px]">curl</span>}>
        <div className="mb-2 flex justify-end">
          <CopyButton text={buildCurl(job)} />
        </div>
        <pre className="text-mono-num max-h-56 overflow-auto rounded-[var(--radius-sm)] border border-border bg-inset p-3 text-[11px] leading-relaxed text-text-secondary">
          {buildCurl(job)}
        </pre>
        <p className="mt-2 text-[11px] text-text-tertiary">
          The exact request behind this result. Poll{" "}
          <span className="text-mono-num">GET /v1/analyses/{"{id}"}</span> for
          status.
        </p>
      </Disclosure>

      <Disclosure title="View JSON">
        <div className="mb-2 flex justify-end">
          <CopyButton text={JSON.stringify(job, null, 2)} />
        </div>
        <pre className="text-mono-num max-h-72 overflow-auto rounded-[var(--radius-sm)] border border-border bg-inset p-3 text-[11px] leading-relaxed text-text-secondary">
          {JSON.stringify(job, null, 2)}
        </pre>
      </Disclosure>
    </div>
  );
}
