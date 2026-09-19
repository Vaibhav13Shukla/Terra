"use client";

import { useEffect, useRef, useState } from "react";
import { useWorkspaceStore } from "@/lib/workspaceStore";
import { terraApi, ApiError } from "@/lib/api";
import type { AnalysisJob, AnalysisType } from "@/lib/types";

const TERMINAL_STATUSES = new Set(["completed", "failed"]);

function todayMinus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function StatusBadge({ status }: { status: AnalysisJob["status"] }) {
  const color =
    status === "completed"
      ? "text-positive border-positive/40"
      : status === "failed"
        ? "text-negative border-negative/40"
        : "text-text-secondary border-border-strong";
  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${color}`}
    >
      {status}
    </span>
  );
}

function QuestionForm() {
  const { aoi, setJob, setPolling, setError } = useWorkspaceStore();
  const [question, setQuestion] = useState(
    "How has vegetation changed here?"
  );
  const [analysisType, setAnalysisType] = useState<AnalysisType | "">("");
  const [provider, setProvider] = useState("fixtures");
  const [startDate, setStartDate] = useState(todayMinus(31));
  const [endDate, setEndDate] = useState(todayMinus(1));
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!aoi) return;
    setSubmitting(true);
    setError(null);
    try {
      const job = await terraApi.createAnalysis({
        aoi,
        start_date: startDate,
        end_date: endDate,
        provider,
        ...(analysisType ? { analysis: analysisType } : { question }),
      });
      setJob(job);
      if (!TERMINAL_STATUSES.has(job.status)) setPolling(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not reach the API"
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <label className="block text-sm">
        <span className="mb-1.5 block text-text-secondary">Question</span>
        <input
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value);
            setAnalysisType("");
          }}
          className="w-full rounded-[var(--radius-sm)] border border-border bg-inset px-3 py-2.5 text-sm outline-none focus:border-border-strong"
          placeholder="How has vegetation changed here?"
        />
      </label>

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

      <label className="block text-sm">
        <span className="mb-1.5 block text-text-secondary">Provider</span>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="w-full rounded-[var(--radius-sm)] border border-border bg-inset px-3 py-2.5 text-sm outline-none focus:border-border-strong"
        >
          <option value="fixtures">fixtures (deterministic demo)</option>
          <option value="sentinel-2-l2a">sentinel-2-l2a (live)</option>
        </select>
      </label>

      <button
        type="submit"
        disabled={!aoi || submitting}
        className="w-full rounded-[var(--radius-sm)] border border-text-primary bg-text-primary py-2.5 text-sm font-medium text-canvas transition hover:opacity-90 disabled:opacity-40"
      >
        {!aoi
          ? "Draw an area on the map first"
          : submitting
            ? "Running analysis…"
            : "Run analysis"}
      </button>
    </form>
  );
}

function ResultView({ job }: { job: AnalysisJob }) {
  const [expanded, setExpanded] = useState(false);
  const result = job.result;
  const metric = result?.metric;
  const change = metric?.percentage_change;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <span className="text-mono-num text-xs text-text-tertiary">
          {job.job_id.slice(0, 8)}
        </span>
        <StatusBadge status={job.status} />
      </div>

      {metric && (
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
              ? `${change > 0 ? "+" : ""}${change}%`
              : metric.current_value}
          </p>
          {metric.comparison_value !== null &&
            metric.comparison_value !== undefined && (
              <p className="text-mono-num mt-1 text-xs text-text-secondary">
                {metric.comparison_value} &rarr; {metric.current_value}
              </p>
            )}
        </div>
      )}

      {result?.message && (
        <p className="text-sm text-text-secondary">{result.message}</p>
      )}
      {result?.explanation && (
        <p className="border-t border-border pt-4 text-sm leading-relaxed text-text-secondary">
          {result.explanation}
        </p>
      )}

      {result?.data_quality && (
        <div className="grid grid-cols-3 gap-3 border-t border-border pt-4 text-sm">
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
            <p className="text-xs text-text-tertiary">valid pixels</p>
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

      {result?.evidence && result.evidence.scenes.length > 0 && (
        <div className="border-t border-border pt-4">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex w-full items-center justify-between text-sm font-medium text-text-primary"
          >
            <span>Evidence ({result.evidence.scenes.length} scenes)</span>
            <span className="text-text-tertiary">{expanded ? "−" : "+"}</span>
          </button>
          {expanded && (
            <ul className="mt-3 space-y-2">
              {result.evidence.scenes.map((s) => (
                <li
                  key={s.id}
                  className="panel flex items-center justify-between px-3 py-2 text-xs"
                >
                  <div>
                    <p className="text-mono-num text-text-primary">
                      {s.id.length > 24 ? `${s.id.slice(0, 24)}…` : s.id}
                    </p>
                    <p className="text-text-tertiary">
                      {new Date(s.datetime).toLocaleDateString()}
                      {s.cloud_cover !== null &&
                        ` · ${s.cloud_cover.toFixed(0)}% cloud`}
                    </p>
                    {s.rejection_reason && (
                      <p className="mt-1 text-warning">{s.rejection_reason}</p>
                    )}
                  </div>
                  <span
                    className={`text-mono-num ${s.selected ? "text-positive" : "text-text-tertiary"}`}
                  >
                    {s.selected ? "used" : "rejected"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function InspectorPanel() {
  const { job, polling, setJob, setPolling, error } = useWorkspaceStore();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!polling || !job) return;
    intervalRef.current = setInterval(async () => {
      try {
        const updated = await terraApi.getAnalysis(job.job_id);
        setJob(updated);
        if (TERMINAL_STATUSES.has(updated.status)) {
          setPolling(false);
        }
      } catch {
        setPolling(false);
      }
    }, 2500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [polling, job, setJob, setPolling]);

  return (
    <aside className="glass-panel flex h-full w-[380px] flex-col overflow-y-auto p-6">
      <h2 className="text-sm font-medium text-text-primary">
        {job ? "Analysis" : "New analysis"}
      </h2>
      <div className="mt-5">
        {!job && <QuestionForm />}
        {job && <ResultView job={job} />}
      </div>
      {error && (
        <p className="mt-4 text-sm text-negative">{error}</p>
      )}
      {job && (
        <button
          onClick={() => useWorkspaceStore.getState().reset()}
          className="mt-6 text-xs text-text-tertiary transition hover:text-text-primary"
        >
          &larr; New analysis
        </button>
      )}
    </aside>
  );
}
