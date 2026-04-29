import logging
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import JSONResponse

from backend.detector.evidence_summary import (
    analyze_model_robustness,
    assess_result_reliability,
    build_model_evidence,
    generate_final_report,
    generate_user_summary,
)
from backend.detector.postprocess import postprocess_prediction
from backend.detector.predict import ModelUnavailableError, predict_scores
from backend.detector.preprocess import preprocess_image
from backend.detector.report_builder import generate_official_analysis_report
from backend.schemas import (
    ACCEPTED_IMAGE_MIME_TYPES,
    ELAHeatmap,
    ELAMetadata,
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


def _provenance_ai_override(forensic_tests: list[dict[str, Any]]) -> float | None:
    for test in forensic_tests:
        test_name = str(test.get("test_name", "")).lower()
        if "provenance" not in test_name and "watermark" not in test_name:
            continue
        if test.get("verdict") != "suspicious":
            continue

        confidence = float(test.get("confidence", 0.0)) * 100.0
        score = float(test.get("score", 0.0)) * 100.0
        return max(confidence, score)
    return None


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
            request_id=request_id,
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
            allow_fallback=os.getenv("DETECTOR_DISABLE_FALLBACK", "1") != "1",
        )
        threshold = _classification_threshold(used_fallback=prediction.used_fallback)
        postprocessed = postprocess_prediction(prediction=prediction, threshold=threshold)
        model_evidence = build_model_evidence(prediction=prediction, threshold=threshold)
        provider_is_ai = prediction.raw_scores.get("provider_is_ai")
        forensic_tests = list(preprocess_result.metadata.get("forensic_tests", []))
        provenance_override_confidence = _provenance_ai_override(forensic_tests)
        allow_fallback = os.getenv("DETECTOR_DISABLE_FALLBACK", "1") != "1"
        robustness = analyze_model_robustness(
            image_bytes=image_bytes,
            mime_type=mime_type,
            base_prediction=prediction,
            threshold=threshold,
            predict_fn=predict_scores,
            deterministic_seed=deterministic_seed,
            allow_fallback=allow_fallback,
        )
        final_is_ai = (
            bool(provider_is_ai)
            if prediction.model_name == "bitmind_api" and provider_is_ai is not None
            else postprocessed.isAIGenerated
        )
        response_confidence = (
            float(prediction.raw_scores.get("provider_confidence", postprocessed.confidence))
            if prediction.model_name == "bitmind_api" and provider_is_ai is not None
            else postprocessed.confidence
        )
        if provenance_override_confidence is not None:
            final_is_ai = True
            response_confidence = max(response_confidence, round(provenance_override_confidence, 2))
        elif isinstance(robustness.get("confidenceCap"), (int, float)):
            response_confidence = min(response_confidence, float(robustness["confidenceCap"]))

        reliability = assess_result_reliability(
            model_evidence=model_evidence,
            final_is_ai=final_is_ai,
            response_confidence=response_confidence,
            forensic_tests=forensic_tests,
            robustness=robustness,
        )
        report = generate_final_report(
            prediction,
            forensic_tests,
            final_is_ai=final_is_ai,
            final_confidence=response_confidence,
        )
        official_report = generate_official_analysis_report(file.filename or "uploaded-image", report)
        user_summary = generate_user_summary(report)

        ela_metadata = None
        ela_payload = preprocess_result.metadata.get("ela", {})
        heatmap_payload = ela_payload.get("heatmap", {})
        if heatmap_payload:
            heatmap_url = str(heatmap_payload.get("url", ""))
            ela_metadata = ELAMetadata(
                score=round(float(ela_payload.get("score", 0.0)), 2),
                explanation=str(ela_payload.get("explanation", "")),
                metrics=dict(ela_payload.get("metrics", {})),
                heatmap=ELAHeatmap(url=heatmap_url),
            )

        response = DetectionResponse(
            isAIGenerated=final_is_ai,
            confidence=response_confidence,
            indicators=postprocessed.indicators,
            forensic_tests=forensic_tests,
            metadata=DetectionMetadata(
                requestId=request_id,
                fileName=file.filename or "uploaded-image",
                fileSize=file_size,
                mimeType=mime_type,
                modelName=prediction.model_name,
                usedFallback=prediction.used_fallback,
                deterministicSeed=deterministic_seed,
                ela=ela_metadata,
                modelEvidence=model_evidence,
                robustness=robustness,
                reliability=reliability,
                officialReport=official_report,
                userSummary=user_summary,
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
