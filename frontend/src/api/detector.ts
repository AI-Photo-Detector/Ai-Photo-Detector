export interface DetectorIndicator {
  label: string;
  value: number;
  status: "pass" | "warning" | "fail";
}

export interface DetectImageResponse {
  isAIGenerated: boolean;
  confidence: number;
  indicators: DetectorIndicator[];
  metadata?: {
    requestId: string;
    fileName: string;
    fileSize: number;
    mimeType: string;
    modelName?: string;
    usedFallback?: boolean;
    deterministicSeed?: number;
  };
}

interface DetectImageError {
  error_code?: string;
  message?: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function detectImage(file: File): Promise<DetectImageResponse> {
  const body = new FormData();
  body.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/detect`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    let errorPayload: DetectImageError | null = null;

    try {
      errorPayload = (await response.json()) as DetectImageError;
    } catch {
      errorPayload = null;
    }

    const errorCode = errorPayload?.error_code;
    const message = errorPayload?.message ?? `Request failed with status ${response.status}`;
    throw new Error(errorCode ? `${message} (${errorCode})` : message);
  }

  return (await response.json()) as DetectImageResponse;
}
