import type { AnalysisJob, AnalysisType, DateRange, JobStatus } from "./types";

/** Statuses after which a job will never change again — polling can stop. */
export const TERMINAL_STATUSES: ReadonlySet<JobStatus> = new Set<JobStatus>([
  "completed",
  "failed",
]);

/** True while a job is still queued or being processed. In async mode
 *  (TERRA_PROCESSING_MODE=async) the POST returns a "created" job with no
 *  result and a worker finishes it later; the UI must say so, not sit blank. */
export function isRunning(job: AnalysisJob): boolean {
  return !TERMINAL_STATUSES.has(job.status);
}

/** Human wording for a job status. "created" means accepted and waiting for a
 *  worker, which reads better as "queued". */
export function statusLabel(status: JobStatus): string {
  return status === "created" ? "queued" : status;
}

// Dates from the API are plain YYYY-MM-DD calendar dates. Parse and format
// them in UTC so a viewer in any timezone sees the same day the backend used
// (formatting local-time would shift e.g. 2025-08-01 to Jul 31 west of UTC).
function parseDay(d: string): Date {
  return new Date(`${d}T00:00:00Z`);
}

const SHORT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});
const FULL = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export function formatRange(range: DateRange): string {
  return `${SHORT.format(parseDay(range.start))} – ${FULL.format(parseDay(range.end))}`;
}

export function analysisLabel(type: AnalysisType): string {
  return type === "ndvi_change"
    ? "Vegetation change (NDVI)"
    : "Vegetation snapshot (NDVI)";
}

export function isFixtureProvider(provider: string): boolean {
  return provider === "fixtures";
}

export function providerLabel(provider: string): string {
  return isFixtureProvider(provider) ? "Fixture data" : "Sentinel-2 (live)";
}

/**
 * The backend appends each result's limitations to its plain-language
 * explanation, and the UI also renders limitations in their own prominent
 * callout — so without this the same caveat shows twice in one panel. Strip
 * the exact limitation sentences out of the explanation text; the callout
 * keeps them, so no caveat is ever lost.
 */
export function stripLimitations(
  explanation: string,
  limitations: string[]
): string {
  let text = explanation;
  for (const limitation of limitations) {
    text = text.replace(limitation, "");
  }
  return text.replace(/\s{2,}/g, " ").trim();
}

/** Signed percentage with one decimal, e.g. "-18.0%" / "+7.2%". */
export function formatPercent(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
}

/** True when the job ran but the analysis found nothing to compute (or the job
 *  itself failed) — i.e. there is no number to show. */
export function hasNoData(job: AnalysisJob): boolean {
  return job.status === "failed" || job.result?.status === "failed";
}

/** The single most important number of a job, for compact rows (history). */
export function headline(job: AnalysisJob): string {
  const metric = job.result?.metric;
  if (!metric) return hasNoData(job) ? "no data" : "—";
  if (metric.percentage_change !== null && metric.percentage_change !== undefined) {
    return formatPercent(metric.percentage_change);
  }
  return `${metric.name} ${metric.current_value.toFixed(3)}`;
}
