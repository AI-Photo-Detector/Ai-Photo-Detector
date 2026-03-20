from backend.detector.postprocess import PostprocessOutput
from backend.detector.predict import PredictionOutput
from backend.detector.preprocess import PreprocessOutput
from backend.schemas import MAX_UPLOAD_SIZE_BYTES


def test_detect_success(client, sample_png_bytes, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.preprocess_image",
        lambda **kwargs: PreprocessOutput(
            model_input={"entropy": 1.0, "zero_ratio": 0.5, "size_log": 1.0, "size_norm": 0.1},
            metadata={"mime_type": "image/png", "byte_length": len(sample_png_bytes), "deterministic": False},
        ),
    )
    monkeypatch.setattr(
        "backend.routes.predict_scores",
        lambda **kwargs: PredictionOutput(
            ai_probability=84.62,
            raw_scores={"ai_probability": 84.62},
            model_name="configured_model",
            used_fallback=False,
        ),
    )
    monkeypatch.setattr(
        "backend.routes.postprocess_prediction",
        lambda **kwargs: PostprocessOutput(
            isAIGenerated=True,
            confidence=84.62,
            indicators=[
                {"label": "Pixel Consistency", "value": 88.39, "status": "pass"},
            ],
        ),
    )

    response = client.post(
        "/api/detect",
        files={"file": ("sample.png", sample_png_bytes, "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["isAIGenerated"] is True
    assert payload["confidence"] == 84.62
    assert payload["indicators"][0]["label"] == "Pixel Consistency"
    assert payload["metadata"]["fileName"] == "sample.png"
    assert payload["metadata"]["fileSize"] == len(sample_png_bytes)
    assert payload["metadata"]["mimeType"] == "image/png"
    assert payload["metadata"]["modelName"] == "configured_model"
    assert payload["metadata"]["usedFallback"] is False
    assert isinstance(payload["metadata"]["requestId"], str)


def test_detect_missing_file_returns_400(client):
    response = client.post("/api/detect")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "MISSING_FILE"
    assert payload["message"] == "No file was uploaded."
    assert isinstance(payload["details"]["requestId"], str)


def test_detect_unsupported_type_returns_415(client):
    response = client.post(
        "/api/detect",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415
    payload = response.json()
    assert payload["error_code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert payload["details"]["mimeType"] == "text/plain"
    assert set(payload["details"]["acceptedMimeTypes"]) == {"image/jpeg", "image/png", "image/webp"}


def test_detect_oversized_file_returns_422(client, monkeypatch):
    monkeypatch.setattr("backend.routes.MAX_UPLOAD_SIZE_BYTES", 16)

    response = client.post(
        "/api/detect",
        files={"file": ("big.png", b"\x89PNG\r\n\x1a\n" + (b"a" * 32), "image/png")},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "FILE_TOO_LARGE"
    assert payload["details"]["maxSizeBytes"] == 16
    assert payload["details"]["fileSizeBytes"] > payload["details"]["maxSizeBytes"]