import { create } from "zustand";
import type { AOI, AnalysisJob } from "./types";

interface WorkspaceState {
  aoi: AOI | null;
  drawing: boolean;
  job: AnalysisJob | null;
  polling: boolean;
  error: string | null;
  setAoi: (aoi: AOI | null) => void;
  setDrawing: (drawing: boolean) => void;
  setJob: (job: AnalysisJob | null) => void;
  setPolling: (polling: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  aoi: null,
  drawing: false,
  job: null,
  polling: false,
  error: null,
  setAoi: (aoi) => set({ aoi }),
  setDrawing: (drawing) => set({ drawing }),
  setJob: (job) => set({ job }),
  setPolling: (polling) => set({ polling }),
  setError: (error) => set({ error }),
  reset: () => set({ aoi: null, job: null, error: null, drawing: false }),
}));
