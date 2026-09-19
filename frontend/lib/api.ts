import { getIdToken } from "./auth";
import type {
  AnalysisJob,
  AnalysisRequestPayload,
  ScenesPreview,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getIdToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const terraApi = {
  health: () => request<{ status: string }>("/health"),

  providers: () => request<{ providers: string[] }>("/v1/providers"),

  scenes: (params: {
    min_lon: number;
    min_lat: number;
    max_lon: number;
    max_lat: number;
    start_date: string;
    end_date: string;
    cloud_threshold?: number;
    provider?: string;
  }) => {
    const search = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    );
    return request<ScenesPreview>(`/v1/scenes?${search.toString()}`);
  },

  createAnalysis: (payload: AnalysisRequestPayload) =>
    request<AnalysisJob>("/v1/analyses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listAnalyses: (limit = 20) =>
    request<AnalysisJob[]>(`/v1/analyses?limit=${limit}`),

  getAnalysis: (jobId: string) =>
    request<AnalysisJob>(`/v1/analyses/${jobId}`),
};

export { ApiError };
