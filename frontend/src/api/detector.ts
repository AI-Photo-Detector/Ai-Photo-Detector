export interface DetectorIndicator {
  label: string;
  value: number;
  status: "pass" | "warning" | "fail";
  explanation?: string;
}

export interface ELAHeatmap {
  url: string;
}

export interface ELAMetadata {
  score: number;
  explanation: string;
  metrics: {
    mean_intensity?: number;
    std_intensity?: number;
    max_intensity?: number;
    p95_intensity?: number;
    hotspot_ratio?: number;
    edge_suppressed_hotspot_ratio?: number;
    block_variation?: number;
    cross_quality_std?: number;
  };
  heatmap: ELAHeatmap;
}

export interface ForensicTest {
  test_name: string;
  score: number;
  confidence: number;
  verdict: "clean" | "suspicious" | "inconclusive";
  details: Record<string, unknown>;
}

export interface ModelEvidence {
  provider?: string;
  rawAiProbability: number;
  providerScore?: number | null;
  providerVerdict?: string | null;
  providerConfidence?: number | null;
  threshold: number;
  usedFallback: boolean;
  signalStrength: "strong" | "moderate" | "weak" | "inconclusive" | string;
  explanation: string;
}

export interface RobustnessVariant {
  name: string;
  aiProbability: number;
  verdict: string;
}

export interface RobustnessCheck {
  status: "stable" | "mixed" | "unstable" | "unavailable" | "disabled" | string;
  label: string;
  score: number;
  minAiProbability?: number | null;
  maxAiProbability?: number | null;
  spread?: number | null;
  variantCount: number;
  variants: RobustnessVariant[];
  confidenceCap?: number | null;
  errors: string[];
  explanation: string;
}

export interface ResultReliability {
  level: "high" | "medium" | "low" | "inconclusive" | "conflicting" | string;
  label: string;
  score: number;
  explanation: string;
  factors: string[];
}

export interface UserSummary {
  "Final Verdict": string;
  Confidence: string;
  Summary: string;
  "Forensic Insight": string;
  Recommendation: string;
}

export interface DetectImageResponse {
  isAIGenerated: boolean;
  confidence: number;
  indicators: DetectorIndicator[];
  forensic_tests?: ForensicTest[];
  metadata?: {
    requestId: string;
    fileName: string;
    fileSize: number;
    mimeType: string;
    modelName?: string;
    usedFallback?: boolean;
    deterministicSeed?: number;
    ela?: ELAMetadata;
    modelEvidence?: ModelEvidence;
    robustness?: RobustnessCheck;
    reliability?: ResultReliability;
    officialReport?: string;
    userSummary?: UserSummary;
  };
}

interface DetectImageErrorPayload {
  error_code?: string;
  message?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class DetectImageError extends Error {
  status: number;
  errorCode?: string;

  constructor(message: string, status: number, errorCode?: string) {
    super(message);
    this.name = "DetectImageError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export async function detectImage(file: File): Promise<DetectImageResponse> {
  const body = new FormData();
  body.append("file", file);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60_000);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/detect`, {
      method: "POST",
      body,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new DetectImageError(
        "The backend did not respond in time. Please try again.",
        0,
        "REQUEST_TIMEOUT"
      );
    }

    throw new DetectImageError(
      "Cannot connect to the backend. Make sure the API server is running.",
      0,
      "BACKEND_OFFLINE"
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    let errorPayload: DetectImageErrorPayload | null = null;

    try {
      errorPayload = (await response.json()) as DetectImageErrorPayload;
    } catch {
      errorPayload = null;
    }

    const errorCode = errorPayload?.error_code;
    const message = errorPayload?.message ?? `Request failed with status ${response.status}`;
    throw new DetectImageError(message, response.status, errorCode);
  }

  return (await response.json()) as DetectImageResponse;
}
