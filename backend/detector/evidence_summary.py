import io
import math
import os
from collections.abc import Callable
from typing import Any

from PIL import Image

from backend.detector.predict import ModelUnavailableError, PredictionOutput


PredictFn = Callable[..., PredictionOutput]


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _signal_confidence(prediction: PredictionOutput) -> float:
    provider_confidence = _to_float(prediction.raw_scores.get("provider_confidence"))
    if provider_confidence is not None:
        return _clamp(provider_confidence, 0.0, 100.0)
    return max(prediction.ai_probability, 100.0 - prediction.ai_probability)


def _signal_strength(confidence: float) -> str:
    if confidence >= 90.0:
        return "strong"
    if confidence >= 75.0:
        return "moderate"
    if confidence >= 60.0:
        return "weak"
    return "inconclusive"


def _provider_verdict(prediction: PredictionOutput, threshold: float) -> str:
    provider_is_ai = prediction.raw_scores.get("provider_is_ai")
    if isinstance(provider_is_ai, bool):
        return "AI Generated" if provider_is_ai else "Low AI Signal"
    return "AI Generated" if prediction.ai_probability >= threshold else "Low AI Signal"


def build_model_evidence(*, prediction: PredictionOutput, threshold: float) -> dict[str, Any]:
    signal_confidence = _signal_confidence(prediction)
    signal_strength = _signal_strength(signal_confidence)
    provider_verdict = _provider_verdict(prediction, threshold)
    provider_score = _to_float(prediction.raw_scores.get("provider_score"))

    if prediction.used_fallback:
        explanation = "Fallback scoring was used because the configured model provider was unavailable."
    elif signal_strength == "strong":
        explanation = "The primary model returned a strong signal away from the decision boundary."
    elif signal_strength == "moderate":
        explanation = "The primary model returned a usable signal, but it is not a maximum-confidence result."
    elif signal_strength == "weak":
        explanation = "The primary model result is close enough to the decision boundary that supporting evidence matters."
    else:
        explanation = "The primary model result is near the decision boundary and should be treated as inconclusive."

    return {
        "provider": prediction.model_name,
        "rawAiProbability": round(_clamp(prediction.ai_probability, 0.0, 100.0), 2),
        "providerScore": round(_clamp(provider_score, 0.0, 100.0), 2) if provider_score is not None else None,
        "providerVerdict": provider_verdict,
        "providerConfidence": round(signal_confidence, 2),
        "threshold": round(threshold, 2),
        "usedFallback": prediction.used_fallback,
        "signalStrength": signal_strength,
        "explanation": explanation,
    }


def _entropy(sample: bytes) -> float:
    if not sample:
        return 0.0

    histogram = [0] * 256
    for byte in sample:
        histogram[byte] += 1

    entropy = 0.0
    sample_size = len(sample)
    for count in histogram:
        if count:
            p = count / sample_size
            entropy -= p * math.log2(p)
    return entropy


def _model_input_for_bytes(image_bytes: bytes) -> dict[str, float]:
    byte_length = max(1, len(image_bytes))
    return {
        "entropy": _entropy(image_bytes[: min(4096, byte_length)]),
        "zero_ratio": image_bytes.count(0) / byte_length,
        "size_log": math.log1p(byte_length),
        "size_norm": min(1.0, byte_length / (10 * 1024 * 1024)),
    }


def _encode_image(image: Image.Image, *, mime_type: str, quality: int = 92) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    if mime_type == "image/png":
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "image/png"
    if mime_type == "image/webp":
        image.save(buffer, format="WEBP", quality=quality)
        return buffer.getvalue(), "image/webp"

    image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def _variant_images(image_bytes: bytes, mime_type: str) -> list[tuple[str, bytes, str]]:
    variants: list[tuple[str, bytes, str]] = []
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            rgb_image = image.convert("RGB")
            rgb_image.load()
    except OSError:
        return variants

    width, height = rgb_image.size
    if width < 24 or height < 24:
        return variants

    resized = rgb_image.resize(
        (max(16, round(width * 0.75)), max(16, round(height * 0.75))),
        Image.Resampling.LANCZOS,
    )
    variants.append(("resized", *_encode_image(resized, mime_type=mime_type)))
    variants.append(("jpeg recompressed", *_encode_image(rgb_image, mime_type="image/jpeg", quality=86)))

    crop_w = max(16, round(width * 0.78))
    crop_h = max(16, round(height * 0.78))
    left = max(0, (width - crop_w) // 2)
    top = max(0, (height - crop_h) // 2)
    center_crop = rgb_image.crop((left, top, min(width, left + crop_w), min(height, top + crop_h)))
    variants.append(("center crop", *_encode_image(center_crop, mime_type=mime_type)))

    if width >= 96 and height >= 96:
        mid_x = width // 2
        mid_y = height // 2
        quadrant_boxes = [
            ("top left crop", (0, 0, mid_x, mid_y)),
            ("top right crop", (mid_x, 0, width, mid_y)),
            ("bottom left crop", (0, mid_y, mid_x, height)),
            ("bottom right crop", (mid_x, mid_y, width, height)),
        ]
        for label, box in quadrant_boxes:
            variants.append((label, *_encode_image(rgb_image.crop(box), mime_type=mime_type)))

    try:
        max_variants = int(os.getenv("DETECTOR_ROBUSTNESS_MAX_VARIANTS", "7"))
    except ValueError:
        max_variants = 7
    return variants[: max(0, max_variants)]


def analyze_model_robustness(
    *,
    image_bytes: bytes,
    mime_type: str,
    base_prediction: PredictionOutput,
    threshold: float,
    predict_fn: PredictFn,
    deterministic_seed: int | None,
    allow_fallback: bool,
) -> dict[str, Any]:
    if os.getenv("DETECTOR_DISABLE_ROBUSTNESS", "0") == "1":
        return {
            "status": "disabled",
            "label": "stability not checked",
            "score": 0.0,
            "variantCount": 1,
            "variants": [
                {
                    "name": "original",
                    "aiProbability": round(base_prediction.ai_probability, 2),
                    "verdict": _provider_verdict(base_prediction, threshold),
                }
            ],
            "explanation": "Robustness analysis is disabled.",
        }

    variant_results = [
        {
            "name": "original",
            "aiProbability": round(base_prediction.ai_probability, 2),
            "verdict": _provider_verdict(base_prediction, threshold),
        }
    ]
    errors: list[str] = []

    for name, variant_bytes, variant_mime_type in _variant_images(image_bytes, mime_type):
        try:
            prediction = predict_fn(
                model_input=_model_input_for_bytes(variant_bytes),
                metadata={
                    "image_bytes": variant_bytes,
                    "mime_type": variant_mime_type,
                    "robustness_variant": name,
                },
                deterministic_seed=deterministic_seed,
                allow_fallback=allow_fallback,
            )
        except ModelUnavailableError as exc:
            errors.append(f"{name}: {exc}")
            continue

        variant_results.append(
            {
                "name": name,
                "aiProbability": round(_clamp(prediction.ai_probability, 0.0, 100.0), 2),
                "verdict": _provider_verdict(prediction, threshold),
            }
        )

    scores = [float(result["aiProbability"]) for result in variant_results]
    if len(scores) < 2:
        return {
            "status": "unavailable",
            "label": "stability unavailable",
            "score": 0.0,
            "variantCount": len(variant_results),
            "variants": variant_results,
            "errors": errors[:3],
            "explanation": "The detector could not score enough image variants for a stability check.",
        }

    min_score = min(scores)
    max_score = max(scores)
    spread = max_score - min_score
    base_verdict = variant_results[0]["verdict"]
    verdict_flip = any(result["verdict"] != base_verdict for result in variant_results[1:])
    stability_score = _clamp(1.0 - (spread / 45.0) - (0.28 if verdict_flip else 0.0), 0.0, 1.0)

    if verdict_flip or spread >= 28.0:
        status = "unstable"
        label = "unstable model signal"
        confidence_cap = 68.0
        explanation = "The model changed substantially across safe image variants, so the result should be treated cautiously."
    elif spread >= 14.0:
        status = "mixed"
        label = "mostly stable signal"
        confidence_cap = 82.0
        explanation = "The model remained directionally consistent, but variant scores moved enough to lower reliability."
    else:
        status = "stable"
        label = "stable AI signal" if base_verdict == "AI Generated" else "stable low AI signal"
        confidence_cap = None
        explanation = "The model stayed consistent across resizing, recompression, and crop checks."

    return {
        "status": status,
        "label": label,
        "score": round(stability_score, 4),
        "minAiProbability": round(min_score, 2),
        "maxAiProbability": round(max_score, 2),
        "spread": round(spread, 2),
        "variantCount": len(variant_results),
        "variants": variant_results,
        "confidenceCap": confidence_cap,
        "errors": errors[:3],
        "explanation": explanation,
    }


def _find_provenance_test(forensic_tests: list[dict[str, Any]]) -> dict[str, Any] | None:
    for test in forensic_tests:
        name = str(test.get("test_name", "")).lower()
        if "provenance" in name or "watermark" in name:
            return test
    return None


def _c2pa_metric(provenance_test: dict[str, Any] | None, key: str) -> Any:
    if not provenance_test:
        return None
    details = provenance_test.get("details")
    if not isinstance(details, dict):
        return None
    metrics = details.get("metrics")
    if not isinstance(metrics, dict):
        return None
    return metrics.get(key)


def assess_result_reliability(
    *,
    model_evidence: dict[str, Any],
    final_is_ai: bool,
    response_confidence: float,
    forensic_tests: list[dict[str, Any]],
    robustness: dict[str, Any] | None,
) -> dict[str, Any]:
    signal_confidence = float(model_evidence.get("providerConfidence") or response_confidence)
    score = _clamp(signal_confidence, 0.0, 100.0)
    factors: list[str] = []

    if model_evidence.get("usedFallback"):
        score = min(score, 55.0)
        factors.append("Fallback model was used.")
    else:
        factors.append(f"Primary model signal is {model_evidence.get('signalStrength', 'unknown')}.")

    provenance_test = _find_provenance_test(forensic_tests)
    provenance_suspicious = provenance_test is not None and provenance_test.get("verdict") == "suspicious"
    c2pa_status = _c2pa_metric(provenance_test, "c2pa_verification_status")
    c2pa_ai_action = _c2pa_metric(provenance_test, "c2pa_ai_action_present") is True
    c2pa_camera_claim = _c2pa_metric(provenance_test, "c2pa_camera_capture_claim_present") is True
    c2pa_signature_valid = _c2pa_metric(provenance_test, "c2pa_signature_valid") is True

    if provenance_suspicious and final_is_ai:
        score = max(score, 94.0)
        factors.append("AI provenance or watermark evidence supports the result.")
    elif provenance_suspicious and not final_is_ai:
        score = min(score, 62.0)
        factors.append("Provenance evidence conflicts with the model result.")
    elif c2pa_signature_valid and c2pa_camera_claim and not final_is_ai:
        score = max(score, 86.0)
        factors.append("Valid camera-capture provenance supports a low-AI result.")
    elif c2pa_status == "unavailable":
        factors.append("C2PA verification tooling was not available.")
    else:
        factors.append("No high-confidence provenance support was found.")

    if c2pa_ai_action:
        score = max(score, 96.0)
        factors.append("Verified C2PA action indicates AI generation or editing.")

    if robustness:
        status = robustness.get("status")
        if status == "stable":
            score = min(100.0, score + 4.0)
            factors.append("Model signal was stable across image variants.")
        elif status == "mixed":
            score = min(score, 78.0)
            factors.append("Variant scores moved enough to reduce reliability.")
        elif status == "unstable":
            score = min(score, 58.0)
            factors.append("Variant scores were unstable.")

    if score >= 88.0:
        level = "high"
        label = "high reliability"
    elif score >= 72.0:
        level = "medium"
        label = "medium reliability"
    elif score >= 55.0:
        level = "low"
        label = "low reliability"
    else:
        level = "inconclusive"
        label = "inconclusive"

    if provenance_suspicious and not final_is_ai:
        level = "conflicting"
        label = "conflicting evidence"

    if level == "high":
        explanation = "The main model result is strong and the supporting evidence does not meaningfully conflict."
    elif level == "medium":
        explanation = "The result is usable, but some evidence is missing or only moderately supportive."
    elif level == "low":
        explanation = "The result should be treated cautiously because the model signal or supporting evidence is limited."
    elif level == "conflicting":
        explanation = "The model result and provenance evidence disagree, so the report should be reviewed manually."
    else:
        explanation = "The report does not have enough stable evidence for a confident AI-vs-real conclusion."

    return {
        "level": level,
        "label": label,
        "score": round(_clamp(score, 0.0, 100.0), 2),
        "explanation": explanation,
        "factors": factors[:5],
    }

def summarize_forensic_results(forensic_tests: list[dict[str, Any]]) -> dict[str, int]:
    """
    Simple aggregation of forensic test verdicts.
    Works with ANY number of tests.
    """

    summary = {
        "total_tests": 0,
        "suspicious_count": 0,
        "clean_count": 0,
        "inconclusive_count": 0,
    }

    for test in forensic_tests:
        verdict = str(test.get("verdict", "")).lower().strip()
        summary["total_tests"] += 1

        if verdict == "suspicious":
            summary["suspicious_count"] += 1
        elif verdict == "clean":
            summary["clean_count"] += 1
        else:
            summary["inconclusive_count"] += 1

    return summary


def build_api_result(prediction: PredictionOutput) -> dict[str, Any]:
    """
    Convert raw model prediction into a clean, frontend-friendly API result.
    """

    verdict = "AI-generated" if prediction.ai_probability >= 50 else "Real"

    return {
        "verdict": verdict,
        "confidence": round(prediction.ai_probability, 2),
        "model": prediction.model_name,
    }


def extract_suspicious_tests(forensic_tests: list[dict[str, Any]]) -> list[str]:
    """
    Return names of forensic tests marked as suspicious.
    """

    suspicious_tests = []

    for test in forensic_tests:
        if str(test.get("verdict", "")).lower() == "suspicious":
            suspicious_tests.append(test.get("test_name", "unknown"))

    return suspicious_tests

def generate_final_report(
    prediction: PredictionOutput,
    forensic_tests: list[dict[str, Any]],
    *,
    final_is_ai: bool | None = None,
    final_confidence: float | None = None,
) -> dict[str, Any]:
    """
    Combine API result and forensic analysis into a final structured report.
    """

    api_result = build_api_result(prediction)
    forensic_summary = summarize_forensic_results(forensic_tests)
    suspicious_tests = extract_suspicious_tests(forensic_tests)

    api_score = prediction.ai_probability / 100.0

    weighted_score_sum = 0.0
    weight_total = 0.0

    for test in forensic_tests:
        test_name = str(test.get("test_name", ""))
        test_score = float(test.get("score", 0.0))

        if test_name == "Semantic Consistency Analysis":
            weight = 0.6
        elif test_name in {
            "Resampling / Scaling Detection",
            "Edge & Boundary Inconsistency Detection",
            "Error Level Analysis",
            "AI Frequency Fingerprint Analysis",
        }:
            weight = 1.0
        else:
            weight = 0.8

        weighted_score_sum += test_score * weight
        weight_total += weight

    forensic_score = weighted_score_sum / max(weight_total, 1e-8)

    final_score = round((api_score * 0.65) + (forensic_score * 0.35), 3)
    final_verdict = "AI-generated" if final_score >= 0.5 else "Real"

    if final_is_ai is not None and final_confidence is not None:
        verdict_confidence = _clamp(float(final_confidence), 0.0, 100.0)
        final_score = round((verdict_confidence if final_is_ai else 100.0 - verdict_confidence) / 100.0, 3)
        final_verdict = "AI-generated" if final_is_ai else "Real"
        api_result["verdict"] = final_verdict
        api_result["confidence"] = round(verdict_confidence, 2)

    explanation = build_explanation(api_result, forensic_summary)

    return {
        "api_result": api_result,
        "forensic_summary": forensic_summary,
        "final_decision": {
            "final_score": final_score,
            "final_verdict": final_verdict,
        },
        "explanation": explanation,
        "suspicious_tests": suspicious_tests,
        "forensic_results": forensic_tests,
    }


def build_explanation(
    api_result: dict[str, Any],
    forensic_summary: dict[str, int],
) -> str:
    """
    Generate a human-readable explanation based on API result and forensic signals.
    """

    suspicious = forensic_summary["suspicious_count"]
    total = max(1, forensic_summary["total_tests"])
    ratio = suspicious / total

    if api_result["verdict"] == "AI-generated":
        if ratio > 0.6:
            return (
                "The AI model indicates a high likelihood of AI generation, "
                "and multiple forensic analyses detected suspicious patterns, "
                "reinforcing this conclusion."
            )
        elif ratio > 0.3:
            return (
                "The AI model suggests the image may be AI-generated, "
                "and some forensic tests found inconsistencies that support this."
            )
        else:
            return (
                "The AI model suggests AI generation, but forensic evidence is limited, "
                "so the result should be interpreted with caution."
            )
    else:
        if ratio < 0.3:
            return (
                "The AI model indicates a low likelihood of AI generation, "
                "and forensic analyses did not detect significant anomalies."
            )
        else:
            return (
                "The AI model suggests the image is real, but some forensic tests detected "
                "inconsistencies that may require further review."
            )


def generate_user_summary(report: dict[str, Any]) -> dict[str, str]:
    """
    Convert full report into a clean, human-readable summary for users.
    """

    final = report["final_decision"]
    suspicious_tests = report.get("suspicious_tests", [])
    forensic_summary = report.get("forensic_summary", {})

    suspicious_count = forensic_summary.get("suspicious_count", 0)
    inconclusive_count = forensic_summary.get("inconclusive_count", 0)
    total_tests = max(1, forensic_summary.get("total_tests", 0))

    forensic_signal_strength = (suspicious_count + (0.5 * inconclusive_count)) / total_tests

    if final["final_verdict"] == "AI-generated":
        confidence_percent = round(final["final_score"] * 100)
    else:
        confidence_percent = round((1 - final["final_score"]) * 100)

    if final["final_verdict"] == "AI-generated":
        if forensic_signal_strength >= 0.35:
            summary = "The image is likely AI-generated based on AI analysis and supporting forensic signals."
        else:
            summary = "The image is likely AI-generated, but this decision is driven mostly by the AI model because forensic evidence is weak."
    else:
        if forensic_signal_strength >= 0.35:
            summary = "The image is likely authentic, although some forensic signals suggest minor irregularities."
        else:
            summary = "The image is likely authentic based on AI analysis and limited forensic concern."

    if suspicious_tests:
        forensic_insight = "Suspicious patterns detected in: " + ", ".join(suspicious_tests)
    elif inconclusive_count > 0:
        forensic_insight = "No strong forensic anomalies detected, but some tests were inconclusive."
    else:
        forensic_insight = "No significant forensic anomalies detected."

    if confidence_percent >= 80:
        recommendation = "High confidence result. No further review needed."
    elif confidence_percent >= 60:
        recommendation = "Moderate confidence. Consider additional verification."
    else:
        recommendation = "Low confidence. Manual review recommended."

    return {
        "Final Verdict": final["final_verdict"],
        "Confidence": f"{confidence_percent}%",
        "Summary": summary,
        "Forensic Insight": forensic_insight,
        "Recommendation": recommendation,
    }
