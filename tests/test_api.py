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
    assert payload["metadata"]["modelEvidence"]["provider"] == "configured_model"
    assert payload["metadata"]["modelEvidence"]["rawAiProbability"] == 84.62
    assert payload["metadata"]["modelEvidence"]["threshold"] == 60.0
    assert payload["metadata"]["robustness"]["status"] in {"stable", "unavailable"}
    assert payload["metadata"]["reliability"]["level"] in {"medium", "high"}
    assert isinstance(payload["metadata"]["requestId"], str)
    assert "artifacts" not in payload["metadata"]


def test_detect_success_returns_inline_ela_heatmap(client, sample_png_bytes, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.preprocess_image",
        lambda **kwargs: PreprocessOutput(
            model_input={"entropy": 1.0, "zero_ratio": 0.5, "size_log": 1.0, "size_norm": 0.1},
            metadata={
                "mime_type": "image/png",
                "byte_length": len(sample_png_bytes),
                "deterministic": False,
                "ela": {
                    "score": 3.2,
                    "explanation": "Low-intensity ELA response.",
                    "metrics": {"mean_intensity": 0.37},
                    "heatmap": {
                        "url": "data:image/png;base64,abc123",
                        "mediaType": "image/png",
                    },
                },
            },
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
    assert payload["metadata"]["ela"]["heatmap"]["url"].startswith("data:image/png;base64,")
    assert "artifacts" not in payload["metadata"]


def test_detect_uses_provider_confidence_when_provider_verdict_is_real(client, sample_png_bytes, monkeypatch):
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
            ai_probability=8.1,
            raw_scores={
                "ai_probability": 8.1,
                "provider_confidence": 91.9,
                "provider_is_ai": False,
            },
            model_name="bitmind_api",
            used_fallback=False,
        ),
    )
    monkeypatch.setattr(
        "backend.routes.postprocess_prediction",
        lambda **kwargs: PostprocessOutput(
            isAIGenerated=False,
            confidence=8.1,
            indicators=[
                {"label": "Pixel Consistency", "value": 12.0, "status": "fail"},
            ],
        ),
    )

    response = client.post(
        "/api/detect",
        files={"file": ("sample.png", sample_png_bytes, "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["isAIGenerated"] is False
    assert payload["confidence"] == 91.9
    assert payload["indicators"][0]["value"] == 12.0
    assert payload["metadata"]["userSummary"]["Final Verdict"] == "Real"
    assert payload["metadata"]["userSummary"]["Confidence"] == "92%"
    assert "Final Verdict: Real" in payload["metadata"]["officialReport"]


def test_detect_ai_provenance_overrides_provider_real_verdict(client, sample_png_bytes, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.preprocess_image",
        lambda **kwargs: PreprocessOutput(
            model_input={
                "entropy": 1.0,
                "zero_ratio": 0.5,
                "size_log": 1.0,
                "size_norm": 0.1,
                "provenance_ai_score": 0.98,
            },
            metadata={
                "mime_type": "image/png",
                "byte_length": len(sample_png_bytes),
                "deterministic": False,
                "forensic_tests": [
                    {
                        "test_name": "Provenance / Watermark Analysis",
                        "score": 0.98,
                        "confidence": 0.96,
                        "verdict": "suspicious",
                        "details": {
                            "provenance_score": 0.98,
                            "explanation": "AI provenance was found.",
                            "metrics": {"ai_metadata_present": True},
                            "indicators": ["OpenAI / DALL-E"],
                        },
                    }
                ],
            },
        ),
    )
    monkeypatch.setattr(
        "backend.routes.predict_scores",
        lambda **kwargs: PredictionOutput(
            ai_probability=8.1,
            raw_scores={
                "ai_probability": 8.1,
                "provider_confidence": 91.9,
                "provider_is_ai": False,
            },
            model_name="bitmind_api",
            used_fallback=False,
        ),
    )
    monkeypatch.setattr(
        "backend.routes.postprocess_prediction",
        lambda **kwargs: PostprocessOutput(
            isAIGenerated=False,
            confidence=8.1,
            indicators=[
                {"label": "Pixel Consistency", "value": 12.0, "status": "fail"},
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
    assert payload["confidence"] == 98.0
    assert payload["forensic_tests"][0]["test_name"] == "Provenance / Watermark Analysis"
    assert payload["metadata"]["userSummary"]["Final Verdict"] == "AI-generated"
    assert payload["metadata"]["userSummary"]["Confidence"] == "98%"
    assert "Final Verdict: AI-generated" in payload["metadata"]["officialReport"]


def test_detect_success_returns_forensic_tests(client, sample_png_bytes, monkeypatch):
    monkeypatch.setattr(
        "backend.routes.preprocess_image",
        lambda **kwargs: PreprocessOutput(
            model_input={
                "entropy": 1.0,
                "zero_ratio": 0.5,
                "size_log": 1.0,
                "size_norm": 0.1,
                "jpeg_compression_inconsistency_score": 0.72,
            },
            metadata={
                "mime_type": "image/png",
                "byte_length": len(sample_png_bytes),
                "deterministic": False,
                "forensic_tests": [
                    {
                        "test_name": "Compression Artifact Analysis",
                        "score": 0.72,
                        "confidence": 0.86,
                        "verdict": "suspicious",
                        "details": {
                            "block_inconsistency_score": 0.72,
                            "artifact_map": {
                                "url": "data:image/png;base64,artifact123",
                                "mediaType": "image/png",
                            },
                            "regions": [{"x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5, "score": 0.9}],
                        },
                    }
                ],
            },
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
    jpeg_test = payload["forensic_tests"][0]
    assert jpeg_test["test_name"] == "Compression Artifact Analysis"
    assert jpeg_test["score"] == 0.72
    assert jpeg_test["details"]["artifact_map"]["url"].startswith("data:image/png;base64,")


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
