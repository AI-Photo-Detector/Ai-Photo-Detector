import math

import pytest

from backend.detector.postprocess import _status_for_value, postprocess_prediction
from backend.detector.predict import ModelUnavailableError, PredictionOutput, predict_scores
from backend.detector.preprocess import preprocess_image


class TestPreprocessImage:
    def test_returns_expected_model_input_and_metadata(self, sample_png_bytes):
        result = preprocess_image(image_bytes=sample_png_bytes, mime_type="image/png")

        assert set(result.model_input) == {"entropy", "zero_ratio", "size_log", "size_norm"}
        assert result.metadata == {
            "mime_type": "image/png",
            "byte_length": len(sample_png_bytes),
            "deterministic": False,
        }
        assert 0.0 <= result.model_input["entropy"] <= 8.0
        assert 0.0 <= result.model_input["zero_ratio"] <= 1.0
        assert result.model_input["size_log"] == pytest.approx(math.log1p(len(sample_png_bytes)))
        assert 0.0 <= result.model_input["size_norm"] <= 1.0

    def test_rejects_empty_bytes(self):
        with pytest.raises(ValueError, match="empty"):
            preprocess_image(image_bytes=b"", mime_type="image/png")

    def test_rejects_unsupported_mime_type(self, sample_png_bytes):
        with pytest.raises(ValueError, match="Unsupported MIME type"):
            preprocess_image(image_bytes=sample_png_bytes, mime_type="image/gif")

    def test_rejects_mime_signature_mismatch(self, sample_png_bytes):
        with pytest.raises(ValueError, match="does not match"):
            preprocess_image(image_bytes=sample_png_bytes, mime_type="image/jpeg")

    def test_accepts_valid_webp_signature(self, sample_webp_bytes):
        result = preprocess_image(
            image_bytes=sample_webp_bytes,
            mime_type="image/webp",
            deterministic=True,
        )

        assert result.metadata["mime_type"] == "image/webp"
        assert result.metadata["deterministic"] is True


class TestPredictScores:
    def test_returns_prediction_contract_from_provider(self, monkeypatch):
        monkeypatch.setenv("BITMIND_API_KEY", "test-key")
        monkeypatch.setattr(
            "backend.detector.predict._run_bitmind_inference",
            lambda api_key, metadata=None: {
                "ai_probability": 61.5,
                "provider_score": 61.5,
                "provider_is_ai": True,
            },
        )

        result = predict_scores(
            model_input={"entropy": 1.0},
            metadata={"image_bytes": b"123", "mime_type": "image/png"},
            allow_fallback=False,
        )

        assert isinstance(result, PredictionOutput)
        assert isinstance(result.ai_probability, float)
        assert isinstance(result.raw_scores, dict)
        assert isinstance(result.model_name, str)
        assert isinstance(result.used_fallback, bool)
        assert result.ai_probability == pytest.approx(61.5)
        assert 0.0 <= result.ai_probability <= 100.0
        assert result.model_name == "bitmind_api"
        assert result.used_fallback is False

    def test_clamps_out_of_range_ai_probability(self, monkeypatch):
        monkeypatch.setenv("BITMIND_API_KEY", "test-key")
        monkeypatch.setattr(
            "backend.detector.predict._run_bitmind_inference",
            lambda api_key, metadata=None: {"ai_probability": 250.0},
        )

        result = predict_scores(
            model_input={"entropy": 1.0},
            metadata={"image_bytes": b"123", "mime_type": "image/png"},
            allow_fallback=False,
        )

        assert result.ai_probability == 100.0

    def test_uses_fallback_when_model_is_unavailable_and_allowed(self, monkeypatch):
        monkeypatch.setenv("BITMIND_API_KEY", "test-key")

        def raise_unavailable(api_key, metadata=None):
            raise ModelUnavailableError("provider unavailable")

        monkeypatch.setattr("backend.detector.predict._run_bitmind_inference", raise_unavailable)
        monkeypatch.setattr(
            "backend.detector.predict._heuristic_inference",
            lambda model_input, deterministic_seed=None: {"ai_probability": 42.0},
        )

        result = predict_scores(
            model_input={"entropy": 1.0},
            metadata={"image_bytes": b"123", "mime_type": "image/png"},
        )

        assert result.ai_probability == 42.0
        assert result.model_name == "heuristic_fallback"
        assert result.used_fallback is True

    def test_raises_when_model_is_unavailable_and_fallback_is_disabled(self, monkeypatch):
        monkeypatch.setenv("BITMIND_API_KEY", "test-key")

        def raise_unavailable(api_key, metadata=None):
            raise ModelUnavailableError("provider unavailable")

        monkeypatch.setattr("backend.detector.predict._run_bitmind_inference", raise_unavailable)

        with pytest.raises(ModelUnavailableError):
            predict_scores(
                model_input={"entropy": 1.0},
                metadata={"image_bytes": b"123", "mime_type": "image/png"},
                allow_fallback=False,
            )


class TestPostprocessPrediction:
    @pytest.mark.parametrize(
        ("value", "expected_status"),
        [
            (49.99, "fail"),
            (50.0, "warning"),
            (74.99, "warning"),
            (75.0, "pass"),
        ],
    )
    def test_status_mapping(self, value, expected_status):
        assert _status_for_value(value) == expected_status

    @pytest.mark.parametrize(
        ("probability", "threshold", "expected"),
        [
            (59.99, 60.0, False),
            (60.0, 60.0, True),
            (84.62, 60.0, True),
            (40.0, 75.0, False),
        ],
    )
    def test_threshold_mapping(self, probability, threshold, expected):
        prediction = PredictionOutput(
            ai_probability=probability,
            raw_scores={"ai_probability": probability},
            model_name="configured_model",
            used_fallback=False,
        )

        result = postprocess_prediction(prediction=prediction, threshold=threshold)

        assert result.isAIGenerated is expected
        assert result.confidence == round(probability, 2)
        assert len(result.indicators) == 5

        for indicator in result.indicators:
            assert isinstance(indicator["label"], str)
            assert isinstance(indicator["value"], float)
            assert indicator["status"] in {"pass", "warning", "fail"}
            assert 0.0 <= indicator["value"] <= 100.0