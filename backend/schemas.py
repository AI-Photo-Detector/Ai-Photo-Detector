<<<<<<< HEAD
# Pydantic BaseModel is used to define
# the exact shape of API responses.
from pydantic import BaseModel


# This ensures every /detect response contains:
# - label (string)
# - confidence (float)
# - method (string)
class DetectionResponse(BaseModel):
    label: str
    confidence: float
    method: str
=======
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

ACCEPTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


class IndicatorStatus(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class Indicator(BaseModel):
    label: str
    value: float = Field(..., ge=0.0, le=100.0)
    status: IndicatorStatus


class DetectionMetadata(BaseModel):
    requestId: str
    fileName: str
    fileSize: int = Field(..., ge=0)
    mimeType: str
    modelName: str | None = None
    usedFallback: bool | None = None
    deterministicSeed: int | None = None


class DetectionResponse(BaseModel):
    isAIGenerated: bool
    confidence: float = Field(..., ge=0.0, le=100.0)
    indicators: list[Indicator]
    metadata: DetectionMetadata | None = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] | None = None
>>>>>>> origin/main
