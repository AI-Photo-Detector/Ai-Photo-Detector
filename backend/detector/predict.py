import os
import random
import base64
from dataclasses import dataclass
from typing import Any

import requests

DEFAULT_BITMIND_API_KEY = "bitmind-bf76cb20-02ac-11f1-83b3-6f90b3a830e0:b504b9e4"


class ModelUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class PredictionOutput:
    ai_probability: float
    raw_scores: dict[str, Any]
    model_name: str
    used_fallback: bool


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _heuristic_inference(model_input: dict[str, float], deterministic_seed: int | None = None) -> dict[str, float]:
    entropy = float(model_input.get("entropy", 0.0))
    zero_ratio = float(model_input.get("zero_ratio", 0.0))
    size_norm = float(model_input.get("size_norm", 0.0))

    entropy_component = _clamp((entropy / 8.0) * 100.0, 0.0, 100.0)
    size_component = _clamp(size_norm * 100.0, 0.0, 100.0)
    zero_component = _clamp((1.0 - zero_ratio) * 100.0, 0.0, 100.0)

    jitter = 0.0
    if deterministic_seed is not None:
        jitter = random.Random(deterministic_seed).uniform(-1.0, 1.0)

    ai_probability = _clamp((entropy_component * 0.5) + (size_component * 0.2) + (zero_component * 0.3) + jitter, 0.0, 100.0)
    return {
        "ai_probability": ai_probability,
        "entropy_component": entropy_component,
        "size_component": size_component,
        "zero_component": zero_component,
    }


def _run_model_inference(model_input: dict[str, float], deterministic_seed: int | None = None) -> dict[str, float]:
    force_unavailable = os.getenv("DETECTOR_FORCE_MODEL_UNAVAILABLE", "0") == "1"
    model_path = os.getenv("DETECTOR_MODEL_PATH")

    if force_unavailable or not model_path or not os.path.exists(model_path):
        raise ModelUnavailableError("Model artifact unavailable.")

    # TODO: Replace with real inference engine call.
    return _heuristic_inference(model_input, deterministic_seed)


def _to_percent(value: float) -> float:
    if 0.0 <= value <= 1.0:
        return value * 100.0
    return value


def _find_probability(payload: Any) -> float | None:
    preferred_keys = {
        "ai_probability",
        "probability",
        "confidence",
        "score",
        "fake_probability",
        "is_ai_probability",
    }

    if isinstance(payload, dict):
        for key, value in payload.items():
            key_l = key.lower()
            if key_l in preferred_keys:
                parsed = _parse_number(value)
                if parsed is not None:
                    return parsed
            if any(token in key_l for token in ("probab", "confid", "score")):
                parsed = _parse_number(value)
                if parsed is not None:
                    return parsed
            found = _find_probability(value)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_probability(item)
            if found is not None:
                return found
    return None


def _parse_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _extract_ai_probability(payload: Any) -> float | None:
    # Handle common classifier-style payloads where label + confidence are returned.
    if isinstance(payload, dict):
        label_keys = ("label", "class", "prediction", "result")
        confidence_keys = ("confidence", "score", "probability", "ai_probability")

        label_value: str | None = None
        confidence_value: float | None = None

        for key in label_keys:
            value = payload.get(key)
            if isinstance(value, str):
                label_value = value.strip().lower()
                break

        for key in confidence_keys:
            value = payload.get(key)
            parsed = _parse_number(value)
            if parsed is not None:
                confidence_value = parsed
                break

        if label_value is not None and confidence_value is not None:
            confidence_pct = _to_percent(confidence_value)
            ai_tokens = ("ai", "fake", "generated", "synthetic")
            real_tokens = ("real", "human", "authentic", "photograph")
            if any(token in label_value for token in ai_tokens):
                return confidence_pct
            if any(token in label_value for token in real_tokens):
                return 100.0 - confidence_pct

    # Fallback to numeric field scan when no label semantics are available.
    return _find_probability(payload)


def _extract_provider_label(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_l = str(key).lower()
            if key_l in {"label", "class", "prediction", "result"} and isinstance(value, str):
                return value.strip().lower()
            found = _extract_provider_label(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_provider_label(item)
            if found:
                return found
    return None


def _extract_provider_is_ai(payload: Any) -> bool | None:
    def _normalize_key(raw_key: Any) -> str:
        return "".join(ch for ch in str(raw_key).lower() if ch.isalnum())

    if isinstance(payload, dict):
        for key, value in payload.items():
            key_l = str(key).lower()
            key_n = _normalize_key(key)

            # Direct boolean verdict keys.
            if key_l in {"is_aigenerated", "is_ai_generated", "is_ai", "ai_generated"} or key_n in {
                "isaigenerated",
                "isaigeneratedimage",
                "isaigeneratedphoto",
                "isai",
                "aigenerated",
            }:
                if isinstance(value, bool):
                    return value
                if isinstance(value, (int, float)):
                    return bool(value)
                if isinstance(value, str):
                    normalized = value.strip().lower()
                    if normalized in {"true", "1", "yes", "ai", "fake"}:
                        return True
                    if normalized in {"false", "0", "no", "real", "human"}:
                        return False

            found = _extract_provider_is_ai(value)
            if found is not None:
                return found

    elif isinstance(payload, list):
        for item in payload:
            found = _extract_provider_is_ai(item)
            if found is not None:
                return found

    label = _extract_provider_label(payload)
    if label:
        if any(token in label for token in ("ai", "fake", "generated", "synthetic")):
            return True
        if any(token in label for token in ("real", "human", "authentic", "photograph")):
            return False
    return None


def _run_bitmind_inference(
    api_key: str,
    *,
    metadata: dict[str, Any] | None,
) -> dict[str, float]:
    if not metadata:
        raise ModelUnavailableError("BitMind inference metadata missing.")

    image_bytes = metadata.get("image_bytes")
    mime_type = metadata.get("mime_type")
    if not isinstance(image_bytes, (bytes, bytearray)) or not isinstance(mime_type, str):
        raise ModelUnavailableError("BitMind inference requires image bytes and mime type.")

    image_b64 = base64.b64encode(bytes(image_bytes)).decode("utf-8")
    payload = {
        "rich": True,
        "source": "local-test-harness",
        "image": f"data:{mime_type};base64,{image_b64}",
    }

    url = os.getenv("BITMIND_DETECT_URL", "https://api.bitmind.ai/oracle/v1/34/detect-image")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "x-bitmind-application": os.getenv("BITMIND_APPLICATION", "oracle-api"),
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    timeout_seconds = float(os.getenv("BITMIND_TIMEOUT_SECONDS", "60"))
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        raise ModelUnavailableError(f"BitMind inference failed: {exc}") from exc
    except ValueError as exc:
        raise ModelUnavailableError("BitMind response was not valid JSON.") from exc

    provider_is_ai = _extract_provider_is_ai(result)
    found_probability = _extract_ai_probability(result)
    if found_probability is None:
        if provider_is_ai is None:
            raise ModelUnavailableError("BitMind response did not include a usable verdict or probability.")
        found_probability = 100.0 if provider_is_ai else 0.0

    ai_probability = _clamp(_to_percent(found_probability), 0.0, 100.0)
    return {
        "ai_probability": ai_probability,
        "provider_score": ai_probability,
        "provider_is_ai": provider_is_ai,
    }


def predict_scores(
    *,
    model_input: dict[str, float],
    metadata: dict[str, Any] | None = None,
    deterministic_seed: int | None = None,
    allow_fallback: bool = True,
) -> PredictionOutput:
    try:
        bitmind_api_key = os.getenv("BITMIND_API_KEY", DEFAULT_BITMIND_API_KEY).strip()
        if bitmind_api_key:
            raw_scores = _run_bitmind_inference(bitmind_api_key, metadata=metadata)
            model_name = "bitmind_api"
        else:
            raw_scores = _run_model_inference(model_input, deterministic_seed)
            model_name = "configured_model"
        used_fallback = False
    except ModelUnavailableError as exc:
        if not allow_fallback:
            raise
        raw_scores = _heuristic_inference(model_input, deterministic_seed)
        model_name = "heuristic_fallback"
        used_fallback = True

    ai_probability = float(raw_scores.get("ai_probability", 0.0))
    ai_probability = _clamp(ai_probability, 0.0, 100.0)

    return PredictionOutput(
        ai_probability=ai_probability,
        raw_scores=raw_scores,
        model_name=model_name,
        used_fallback=used_fallback,
    )
