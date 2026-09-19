import { getIdToken } from "./auth";
import type {
  AnalysisJob,
  AnalysisRequestPayload,
  ScenesPreview,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

/**
 * Turn an API failure into something a user can act on. The backend's own
 * messages for bad input (400 invalid area, 422 unsupported question) are
 * already written for people, so they pass through. A 502 is different: it
 * carries whatever internal exception broke the analysis (e.g. GDAL's "Read
 * failed. See previous exception for details."), which means nothing to a user
 * — that is the satellite data service timing out, so say so.
 */
export function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 502 || err.status === 504) {
      return (
        "The satellite data service didn't respond in time, so this analysis " +
        "couldn't finish. Try again, or draw a smaller area — larger areas " +
        "read more imagery and are more likely to time out."
      );
    }
    if (err.status === 401 || err.status === 403) {
      return "You're not signed in, or your session has expired. Sign in and try again.";
    }
    if (err.status === 429) {
      return "Too many requests right now. Wait a moment and try again.";
    }
    return err.message;
  }
  return "Could not reach the Terra API. Check that the backend is running and NEXT_PUBLIC_API_URL is correct.";
}

export { ApiError };
