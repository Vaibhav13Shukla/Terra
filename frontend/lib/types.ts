// Mirrors backend/app/domain/models.py. Keep in sync manually — regenerate
// against docs/openapi.json if the two drift.

export type AnalysisType = "ndvi_change" | "ndvi_snapshot";

export type JobStatus =
  | "created"
  | "discovering"
  | "processing"
  | "analyzing"
  | "completed"
  | "failed";

export interface AOI {
  type: "Polygon";
  coordinates: [number, number][][];
}

export interface DateRange {
  start: string; // YYYY-MM-DD
  end: string;
}

export interface DataAsset {
  key: string;
  href: string;
  scale: number | null;
  offset: number | null;
}

export interface Scene {
  id: string;
  provider: string;
  datetime: string;
  cloud_cover: number | null;
  assets: Record<string, DataAsset>;
  selected: boolean;
  rejection_reason: string | null;
}

export interface Metric {
  name: string;
  current_value: number;
  comparison_value: number | null;
  absolute_change: number | null;
  percentage_change: number | null;
  unit: string | null;
}

export interface DataQuality {
  scenes_used: number;
  scenes_rejected: number;
  cloud_threshold: number;
  valid_pixel_ratio: number | null;
}

export interface ProcessingStep {
  name: string;
  detail: string;
  duration_ms: number | null;
}

export interface Evidence {
  scenes: Scene[];
  formula: string | null;
  processing_steps: ProcessingStep[];
  bands_used: string[];
}

export interface AnalysisResult {
  analysis_type: AnalysisType;
  status: "success" | "partial" | "failed";
  metric: Metric | null;
  data_quality: DataQuality | null;
  evidence: Evidence | null;
  limitations: string[];
  message: string | null;
  explanation: string | null;
}

export interface AnalysisRequestPayload {
  aoi: AOI;
  start_date: string;
  end_date: string;
  comparison_start_date?: string;
  comparison_end_date?: string;
  analysis?: AnalysisType;
  question?: string;
  cloud_threshold?: number;
  provider?: string;
}

export interface AnalysisRequest {
  aoi: AOI;
  analysis_type: AnalysisType;
  date_range: DateRange;
  comparison_range: DateRange | null;
  cloud_threshold: number;
  provider: string;
}

export interface AnalysisJob {
  job_id: string;
  status: JobStatus;
  request: AnalysisRequest;
  result: AnalysisResult | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScenesPreview {
  selected: Scene[];
  rejected: Scene[];
  scenes_used: number;
  scenes_rejected: number;
}
