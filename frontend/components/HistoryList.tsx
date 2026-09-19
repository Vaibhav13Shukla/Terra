"use client";

import { useEffect, useState } from "react";
import { friendlyError, terraApi } from "@/lib/api";
import {
  analysisLabel,
  formatRange,
  hasNoData,
  headline,
  isFixtureProvider,
} from "@/lib/format";
import type { AnalysisJob } from "@/lib/types";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; jobs: AnalysisJob[] };

export function HistoryList({
  onOpen,
}: {
  onOpen: (job: AnalysisJob) => void;
}) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    terraApi
      .listAnalyses(20)
      .then((jobs) => {
        if (!cancelled) setState({ status: "ready", jobs });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ status: "error", message: friendlyError(err) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.status === "loading") {
    return <p className="text-sm text-text-tertiary">Loading history…</p>;
  }
  if (state.status === "error") {
    return <p className="text-sm text-negative">{state.message}</p>;
  }
  if (state.jobs.length === 0) {
    return (
      <p className="text-sm text-text-tertiary">
        No analyses yet — run one from the New analysis tab.
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {state.jobs.map((job) => {
        const change = job.result?.metric?.percentage_change;
        return (
          <li key={job.job_id}>
            <button
              type="button"
              onClick={() => onOpen(job)}
              className="panel w-full px-3 py-2.5 text-left transition hover:border-border-strong"
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="truncate text-sm text-text-primary">
                  {analysisLabel(job.request.analysis_type)}
                </span>
                <span
                  className={`text-mono-num shrink-0 text-sm ${
                    change === null || change === undefined
                      ? "text-text-secondary"
                      : change < 0
                        ? "text-negative"
                        : "text-positive"
                  }`}
                >
                  {headline(job)}
                </span>
              </div>
              <p className="mt-1 flex items-center gap-2 text-[11px] text-text-tertiary">
                <span>{formatRange(job.request.date_range)}</span>
                <span
                  className={
                    isFixtureProvider(job.request.provider) ? "text-warning" : ""
                  }
                >
                  {isFixtureProvider(job.request.provider) ? "fixture" : "live"}
                </span>
                <span className="ml-auto">
                  {hasNoData(job) && job.status === "completed"
                    ? "no data"
                    : job.status}
                </span>
              </p>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
