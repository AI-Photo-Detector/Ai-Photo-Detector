import logging
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import JSONResponse

from backend.detector.postprocess import postprocess_prediction
from backend.detector.predict import ModelUnavailableError, predict_scores
from backend.detector.preprocess import preprocess_image
from backend.schemas import (
    ACCEPTED_IMAGE_MIME_TYPES,
    MAX_UPLOAD_SIZE_BYTES,
    DetectionMetadata,
    DetectionResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["detector"])


def _error_payload(
    *,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(error_code=error_code, message=message, details=details)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _deterministic_seed() -> int | None:
    raw = os.getenv("DETECTOR_DETERMINISTIC_SEED")
    if raw is None or raw.strip() == "":
        return None

    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("DETECTOR_DETERMINISTIC_SEED must be an integer.") from exc


def _classification_threshold(*, used_fallback: bool) -> float:
    env_key = "DETECTOR_FALLBACK_AI_THRESHOLD" if used_fallback else "DETECTOR_AI_THRESHOLD"
    default_value = "90" if used_fallback else "60"
    raw = os.getenv(env_key, default_value)
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{env_key} must be a number.") from exc


@router.get("/health")
def api_healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/detect", response_model=DetectionResponse)
async def detect_image(file: UploadFile | None = File(default=None)):
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    if file is None:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning("detect_failed request_id=%s reason=missing_file elapsed_ms=%s", request_id, elapsed_ms)
        return _error_payload(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="MISSING_FILE",
            message="No file was uploaded.",
            details={"requestId": request_id},
        )

    mime_type = file.content_type or ""
    if mime_type not in ACCEPTED_IMAGE_MIME_TYPES:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "detect_failed request_id=%s reason=unsupported_mime mime_type=%s elapsed_ms=%s",
            request_id,
            mime_type,
            elapsed_ms,
        )
        return _error_payload(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            error_code="UNSUPPORTED_MEDIA_TYPE",
            message="Unsupported file type.",
            details={
                "requestId": request_id,
                "mimeType": mime_type,
                "acceptedMimeTypes": sorted(ACCEPTED_IMAGE_MIME_TYPES),
            },
        )

    image_bytes = await file.read()
    file_size = len(image_bytes)

    if file_size == 0:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning("detect_failed request_id=%s reason=empty_file elapsed_ms=%s", request_id, elapsed_ms)
        return _error_payload(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="EMPTY_FILE",
            message="Uploaded file is empty.",
            details={"requestId": request_id},
        )

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "detect_failed request_id=%s reason=file_too_large file_size=%s elapsed_ms=%s",
            request_id,
            file_size,
            elapsed_ms,
        )
        return _error_payload(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="FILE_TOO_LARGE",
            message="Uploaded file exceeds max allowed size.",
            details={
                "requestId": request_id,
                "maxSizeBytes": MAX_UPLOAD_SIZE_BYTES,
                "fileSizeBytes": file_size,
            },
        )

    try:
        deterministic_seed = _deterministic_seed()
        preprocess_result = preprocess_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            deterministic=deterministic_seed is not None,
        )
        prediction = predict_scores(
            model_input=preprocess_result.model_input,
            metadata={
                **preprocess_result.metadata,
                "image_bytes": image_bytes,
                "mime_type": mime_type,
            },
            deterministic_seed=deterministic_seed,
            # Default to no fallback so frontend uses provider-backed results
            # instead of silently returning heuristic output.
            allow_fallback=os.getenv("DETECTOR_DISABLE_FALLBACK", "1") != "1",
        )
        threshold = _classification_threshold(used_fallback=prediction.used_fallback)
        postprocessed = postprocess_prediction(prediction=prediction, threshold=threshold)
        provider_is_ai = prediction.raw_scores.get("provider_is_ai")
        final_is_ai = (
            bool(provider_is_ai)
            if prediction.model_name == "bitmind_api" and provider_is_ai is not None
            else postprocessed.isAIGenerated
        )

        response = DetectionResponse(
            isAIGenerated=final_is_ai,
            confidence=postprocessed.confidence,
            indicators=postprocessed.indicators,
            metadata=DetectionMetadata(
                requestId=request_id,
                fileName=file.filename or "uploaded-image",
                fileSize=file_size,
                mimeType=mime_type,
                modelName=prediction.model_name,
                usedFallback=prediction.used_fallback,
                deterministicSeed=deterministic_seed,
            ),
        )

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "detect_success request_id=%s elapsed_ms=%s is_ai=%s confidence=%.2f fallback=%s",
            request_id,
            elapsed_ms,
            response.isAIGenerated,
            response.confidence,
            prediction.used_fallback,
        )
        return response
    except ValueError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "detect_failed request_id=%s reason=validation_error detail=%s elapsed_ms=%s",
            request_id,
            str(exc),
            elapsed_ms,
        )
        return _error_payload(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="INVALID_IMAGE_CONTENT",
            message="Image content failed preprocessing validation.",
            details={"requestId": request_id, "reason": str(exc)},
        )
    except ModelUnavailableError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.error(
            "detect_failed request_id=%s reason=model_unavailable detail=%s elapsed_ms=%s",
            request_id,
            str(exc),
            elapsed_ms,
        )
        return _error_payload(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MODEL_UNAVAILABLE",
            message="Detection model is not available and fallback is disabled.",
            details={"requestId": request_id},
        )
    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception("detect_failed request_id=%s reason=internal_error elapsed_ms=%s", request_id, elapsed_ms)
        return _error_payload(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_ERROR",
            message="Unexpected server error.",
            details={"requestId": request_id},
        )
