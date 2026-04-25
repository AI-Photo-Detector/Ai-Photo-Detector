import base64
import json
import os
from dataclasses import dataclass
from typing import Any

import requests


TEST_NAME = "VLM Visual Review"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class VlmSemanticAnalysis:
    score: float
    confidence: float
    verdict: str
    explanation: str
    metrics: dict[str, float | bool | str]
    observations: list[str]

    def to_forensic_test(self) -> dict[str, Any]:
        return {
            "test_name": TEST_NAME,
            "score": self.score,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "details": {
                "vlm_visual_score": self.score,
                "explanation": self.explanation,
                "observations": self.observations,
                "metrics": self.metrics,
            },
        }


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def should_run_vlm_semantic() -> bool:
    configured = os.getenv("DETECTOR_ENABLE_VLM", "").strip().lower()
    if configured in {"1", "true", "yes", "on"}:
        return True
    return False


def _unavailable_result(*, request_id: str, reason: str) -> VlmSemanticAnalysis:
    return VlmSemanticAnalysis(
        score=0.0,
        confidence=0.0,
        verdict="inconclusive",
        explanation=f"VLM visual review was skipped: {reason}",
        metrics={
            "vlm_model_available": False,
            "vlm_provider": "openai_responses",
            "vlm_status": reason[:220],
            "request_id": request_id,
        },
        observations=[],
    )


def _friendly_unavailable_reason(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        status_code = response.status_code if response is not None else None
        if status_code == 401:
            return "the OpenAI API key was rejected"
        if status_code == 403:
            return "the OpenAI API key does not have access to this model"
        if status_code == 429:
            return "OpenAI rate limit or quota was reached"
        if status_code is not None and status_code >= 500:
            return "OpenAI returned a temporary server error"
    if isinstance(exc, requests.Timeout):
        return "the OpenAI request timed out"
    if isinstance(exc, requests.ConnectionError):
        return "the OpenAI API could not be reached"
    return "the VLM provider response could not be used"


def _response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ai_likelihood": {"type": "integer", "minimum": 0, "maximum": 100},
            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
            "visible_artifact_count": {"type": "integer", "minimum": 0, "maximum": 20},
            "text_anomaly_present": {"type": "boolean"},
            "anatomy_anomaly_present": {"type": "boolean"},
            "reflection_or_shadow_anomaly_present": {"type": "boolean"},
            "geometry_or_perspective_anomaly_present": {"type": "boolean"},
            "notable_observations": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 6,
            },
            "reasoning_summary": {"type": "string"},
        },
        "required": [
            "ai_likelihood",
            "confidence",
            "visible_artifact_count",
            "text_anomaly_present",
            "anatomy_anomaly_present",
            "reflection_or_shadow_anomaly_present",
            "geometry_or_perspective_anomaly_present",
            "notable_observations",
            "reasoning_summary",
        ],
    }


def _prompt() -> str:
    return (
        "Inspect this image as a strict visual artifact review for an AI-photo detector. "
        "Return JSON only. Assume modern AI images can look realistic, so do a careful, skeptical pass over "
        "fine details instead of relying on the overall scene looking natural. Look specifically for subtle "
        "AI-generation or manipulation cues: asymmetrical eyes, teeth, ears, fingers, hair, jewelry, glasses, "
        "fabric seams, logos, readable text, object edges, repeated texture, inconsistent skin pores, waxy or "
        "over-smoothed skin, locally sharp/soft regions, impossible lighting, shadow direction changes, reflection "
        "mismatches, warped perspective, merged objects, background distortions, and repeated or invented details. "
        "For portraits, scrutinize both sides of the face, hairline, eyelashes, ears, hands, clothing edges, and "
        "background continuity. For products or scenes, scrutinize text, symmetry, geometry, reflections, and contact shadows. "
        "Do not use metadata, filename, subject matter, style, beauty, or image quality alone as proof. "
        "If no concrete visible artifact is present, keep ai_likelihood low and say no obvious visual artifacts were found. "
        "If there are only mild cues, return an inconclusive score rather than clean. This is supporting evidence, not standalone proof."
    )


def _build_payload(*, image_bytes: bytes, mime_type: str, model: str) -> dict[str, Any]:
    detail = os.getenv("OPENAI_VLM_DETAIL", "auto").strip().lower()
    if detail not in {"low", "high", "auto"}:
        detail = "auto"

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{image_b64}"

    try:
        max_output_tokens = int(os.getenv("OPENAI_VLM_MAX_OUTPUT_TOKENS", "600"))
    except ValueError:
        max_output_tokens = 600

    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _prompt()},
                    {"type": "input_image", "image_url": data_url, "detail": detail},
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "vlm_visual_review",
                "strict": True,
                "schema": _response_schema(),
            }
        },
        "max_output_tokens": max(120, min(max_output_tokens, 1200)),
    }


def _extract_response_text(payload: Any) -> str | None:
    if isinstance(payload, dict) and isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    texts: list[str] = []
    output = payload.get("output") if isinstance(payload, dict) else None
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                if content_item.get("type") in {"output_text", "text"} and isinstance(content_item.get("text"), str):
                    texts.append(content_item["text"])
    return "\n".join(texts) if texts else None


def _json_from_text(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("VLM response JSON was not an object.")
    return payload


def _bool_value(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True


def _number_value(payload: dict[str, Any], key: str) -> float:
    value = payload.get(key, 0)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return 0.0
    return 0.0


def _observations(payload: dict[str, Any]) -> list[str]:
    values = payload.get("notable_observations")
    if not isinstance(values, list):
        return []
    observations: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        text = " ".join(value.split()).strip()
        if text:
            observations.append(text[:180])
    return observations[:6]


def _verdict_for_review(*, likelihood: float, confidence: float, artifact_count: int) -> str:
    if likelihood >= 70.0 and confidence >= 55.0 and artifact_count >= 1:
        return "suspicious"
    if likelihood >= 35.0 or artifact_count > 0:
        return "inconclusive"
    return "clean"


def _display_score(*, likelihood: float, verdict: str) -> float:
    normalized = _clamp(likelihood / 100.0, 0.0, 1.0)
    if verdict == "suspicious":
        return round(_clamp(normalized, 0.55, 1.0), 4)
    if verdict == "inconclusive":
        return round(_clamp(normalized, 0.25, 0.5), 4)
    return round(_clamp(normalized, 0.0, 0.24), 4)


def _explanation(*, verdict: str, summary: str, confidence: float) -> str:
    summary = " ".join(summary.split()).strip()
    if not summary:
        if verdict == "suspicious":
            summary = "The VLM reported visible anomalies worth reviewing."
        elif verdict == "inconclusive":
            summary = "The VLM review was ambiguous."
        else:
            summary = "The VLM did not report obvious visible AI artifacts."

    if confidence < 40.0:
        return f"{summary} Confidence is low, so treat this as a weak review signal."
    return summary[:360]


def analyze_vlm_semantic(*, image_bytes: bytes, mime_type: str, request_id: str) -> VlmSemanticAnalysis:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _unavailable_result(request_id=request_id, reason="OPENAI_API_KEY is not configured")

    model = os.getenv("OPENAI_VLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    url = os.getenv("OPENAI_VLM_URL", OPENAI_RESPONSES_URL).strip() or OPENAI_RESPONSES_URL
    try:
        timeout_seconds = float(os.getenv("OPENAI_VLM_TIMEOUT_SECONDS", "45"))
    except ValueError:
        timeout_seconds = 45.0

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            json=_build_payload(image_bytes=image_bytes, mime_type=mime_type, model=model),
            headers=headers,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        response_payload = response.json()
        response_text = _extract_response_text(response_payload)
        if response_text is None:
            return _unavailable_result(request_id=request_id, reason="VLM response did not include text output")
        review = _json_from_text(response_text)
    except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError) as exc:
        return _unavailable_result(request_id=request_id, reason=_friendly_unavailable_reason(exc))

    likelihood = _clamp(_number_value(review, "ai_likelihood"), 0.0, 100.0)
    visual_confidence = _clamp(_number_value(review, "confidence"), 0.0, 100.0)
    artifact_count = int(_clamp(_number_value(review, "visible_artifact_count"), 0.0, 20.0))
    observations = _observations(review)
    verdict = _verdict_for_review(
        likelihood=likelihood,
        confidence=visual_confidence,
        artifact_count=artifact_count,
    )
    score = _display_score(likelihood=likelihood, verdict=verdict)
    confidence = round(_clamp(visual_confidence / 100.0, 0.0, 1.0), 4)

    metrics: dict[str, float | bool | str] = {
        "vlm_model_available": True,
        "vlm_provider": "openai_responses",
        "vlm_model": model,
        "ai_likelihood_percent": round(likelihood, 2),
        "visual_confidence_percent": round(visual_confidence, 2),
        "visible_artifact_count": float(artifact_count),
        "text_anomaly_present": _bool_value(review, "text_anomaly_present"),
        "anatomy_anomaly_present": _bool_value(review, "anatomy_anomaly_present"),
        "reflection_or_shadow_anomaly_present": _bool_value(review, "reflection_or_shadow_anomaly_present"),
        "geometry_or_perspective_anomaly_present": _bool_value(review, "geometry_or_perspective_anomaly_present"),
        "request_id": request_id,
    }

    return VlmSemanticAnalysis(
        score=score,
        confidence=confidence,
        verdict=verdict,
        explanation=_explanation(
            verdict=verdict,
            summary=str(review.get("reasoning_summary", "")),
            confidence=visual_confidence,
        ),
        metrics=metrics,
        observations=observations,
    )
