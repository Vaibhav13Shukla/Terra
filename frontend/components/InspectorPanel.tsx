"use client";

import { useEffect, useRef, useState } from "react";
import { useWorkspaceStore } from "@/lib/workspaceStore";
import { terraApi } from "@/lib/api";
import { TERMINAL_STATUSES } from "@/lib/format";
import type { AnalysisJob } from "@/lib/types";
import { HistoryList } from "./HistoryList";
import { QuestionForm } from "./QuestionForm";
import { ResultView } from "./ResultView";

// A single failed poll (a Lambda cold start, a brief 5xx) must not strand a job
// on "queued" forever — but polling also must not hammer a dead API. 2.5 s x 8.
const MAX_CONSECUTIVE_POLL_FAILURES = 8;

type Tab = "new" | "history";

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-[var(--radius-sm)] px-3 py-1.5 text-xs font-medium transition ${
        active
          ? "bg-inset text-text-primary"
          : "text-text-tertiary hover:text-text-secondary"
      }`}
    >
      {children}
    </button>
  );
}

export function InspectorPanel() {
  const { job, polling, setJob, setPolling, setError, error } = useWorkspaceStore();
  const [tab, setTab] = useState<Tab>("new");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const failuresRef = useRef(0);

  // Poll an in-flight job until it reaches a terminal status. With the default
  // synchronous backend the POST already returns a finished job, so this only
  // runs in async mode (TERRA_PROCESSING_MODE=async), where the job starts
  // "created" and a worker completes it.
  useEffect(() => {
    if (!polling || !job) return;
    intervalRef.current = setInterval(async () => {
      try {
        const updated = await terraApi.getAnalysis(job.job_id);
        failuresRef.current = 0;
        setJob(updated);
        if (TERMINAL_STATUSES.has(updated.status)) {
          setPolling(false);
        }
      } catch {
        failuresRef.current += 1;
        if (failuresRef.current >= MAX_CONSECUTIVE_POLL_FAILURES) {
          failuresRef.current = 0;
          setPolling(false);
          setError(
            "Lost contact with the API while waiting for this analysis. It may still be running — open it from History to check.",
          );
        }
      }
    }, 2500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [polling, job, setJob, setPolling, setError]);

  function openFromHistory(selected: AnalysisJob) {
    setJob(selected);
    setPolling(!TERMINAL_STATUSES.has(selected.status));
    setTab("new");
  }

  return (
    <aside className="glass-panel flex h-full w-[380px] shrink-0 flex-col overflow-y-auto p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-text-primary">
          {tab === "history" ? "History" : job ? "Analysis" : "New analysis"}
        </h2>
        <div className="flex gap-1">
          <TabButton active={tab === "new"} onClick={() => setTab("new")}>
            {job ? "Result" : "New"}
          </TabButton>
          <TabButton
            active={tab === "history"}
            onClick={() => setTab("history")}
          >
            History
          </TabButton>
        </div>
      </div>

      <div className="mt-5">
        {tab === "history" ? (
          <HistoryList onOpen={openFromHistory} />
        ) : job ? (
          <ResultView job={job} polling={polling} />
        ) : (
          <QuestionForm />
        )}
      </div>

      {error && tab === "new" && (
        <p className="mt-4 text-sm text-negative">{error}</p>
      )}

      {tab === "new" && job && (
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
