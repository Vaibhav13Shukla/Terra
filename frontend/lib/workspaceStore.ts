import { create } from "zustand";
import type { AOI, AnalysisJob } from "./types";

/** Where the current AOI came from — the map only auto-frames a "demo" AOI
 *  (a field the user drew is, by definition, already in view). */
export type AoiSource = "drawn" | "demo";

interface WorkspaceState {
  aoi: AOI | null;
  aoiSource: AoiSource | null;
  drawing: boolean;
  job: AnalysisJob | null;
  polling: boolean;
  error: string | null;
  setAoi: (aoi: AOI | null, source?: AoiSource) => void;
  setDrawing: (drawing: boolean) => void;
  setJob: (job: AnalysisJob | null) => void;
  setPolling: (polling: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  aoi: null,
  aoiSource: null,
  drawing: false,
  job: null,
  polling: false,
  error: null,
  setAoi: (aoi, source = "drawn") =>
    set({ aoi, aoiSource: aoi ? source : null }),
  setDrawing: (drawing) => set({ drawing }),
  setJob: (job) => set({ job }),
  setPolling: (polling) => set({ polling }),
  setError: (error) => set({ error }),
  reset: () =>
    set({ aoi: null, aoiSource: null, job: null, error: null, drawing: false }),
}));
