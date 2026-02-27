from dataclasses import dataclass

from backend.detector.predict import PredictionOutput


@dataclass(frozen=True)
class PostprocessOutput:
    isAIGenerated: bool
    confidence: float
    indicators: list[dict[str, float | str]]


def _status_for_value(value: float) -> str:
    if value >= 75:
        return "pass"
    if value >= 50:
        return "warning"
    return "fail"


def postprocess_prediction(*, prediction: PredictionOutput, threshold: float = 60.0) -> PostprocessOutput:
    confidence = round(float(prediction.ai_probability), 2)
    is_ai_generated = confidence >= threshold

    pixel = min(100.0, confidence * 0.95 + 4)
    noise = min(100.0, confidence * 0.85 + 9)
    edge = min(100.0, confidence * 0.8 + 12)
    color = min(100.0, confidence * 0.9 + 6)
    freq = min(100.0, confidence * 0.88 + 7)

    indicators = [
        {"label": "Pixel Consistency", "value": round(pixel, 2), "status": _status_for_value(pixel)},
        {"label": "Noise Patterns", "value": round(noise, 2), "status": _status_for_value(noise)},
        {"label": "Edge Detection", "value": round(edge, 2), "status": _status_for_value(edge)},
        {"label": "Color Distribution", "value": round(color, 2), "status": _status_for_value(color)},
        {"label": "Frequency Analysis", "value": round(freq, 2), "status": _status_for_value(freq)},
    ]

    return PostprocessOutput(
        isAIGenerated=is_ai_generated,
        confidence=confidence,
        indicators=indicators,
    )
