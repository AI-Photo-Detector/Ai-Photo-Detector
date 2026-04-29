import io
import json
import math

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, PngImagePlugin

from backend.detector.copy_move import analyze_copy_move, _verdict_for_metrics as _copy_move_verdict_for_metrics
from backend.detector.diffusion_reconstruction import analyze_diffusion_reconstruction
from backend.detector.evidence_summary import build_model_evidence, assess_result_reliability
from backend.detector.ela import analyze_ela, _verdict_for_metrics as _ela_verdict_for_metrics
from backend.detector.frequency_fingerprint import analyze_frequency_fingerprint
from backend.detector.jpeg_artifacts import analyze_jpeg_artifacts, _verdict_for_metrics
from backend.detector.noise_texture import analyze_noise_texture, _verdict_for_metrics as _noise_verdict_for_metrics
from backend.detector.provenance import analyze_provenance
from backend.detector.semantic_consistency import analyze_semantic_consistency
from backend.detector.vlm_semantic import analyze_vlm_semantic, should_run_vlm_semantic
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

    def test_includes_inline_ela_heatmap_when_request_id_is_present(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DETECTOR_ENABLE_VLM", raising=False)
        image = Image.new("RGB", (12, 12), color=(180, 190, 200))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        result = preprocess_image(
            image_bytes=buffer.getvalue(),
            mime_type="image/png",
            request_id="req-123",
        )

        assert "ela" in result.metadata
        heatmap = result.metadata["ela"]["heatmap"]
        assert heatmap["mediaType"] == "image/png"
        assert heatmap["url"].startswith("data:image/png;base64,")
        assert "artifact" not in result.metadata["ela"]
        test_names = [test["test_name"] for test in result.metadata["forensic_tests"]]
        assert test_names == [
            "Provenance / Watermark Analysis",
            "EXIF Metadata Analysis",
            "AI Frequency Fingerprint Analysis",
            "Diffusion Reconstruction Analysis",
            "Semantic Consistency Analysis",
            "Error Level Analysis",
            "Compression Artifact Analysis",
            "Noise Pattern / Texture Consistency Analysis",
            "Resampling / Scaling Detection",
            "Edge & Boundary Inconsistency Detection",
            "Copy-Move (Clone) Detection",
        ]
        assert "noise_texture_inconsistency_score" in result.model_input
        assert "resampling_scaling_score" in result.model_input
        assert "edge_boundary_inconsistency_score" in result.model_input
        assert "copy_move_clone_score" in result.model_input
        assert "provenance_ai_score" in result.model_input
        assert "frequency_fingerprint_score" in result.model_input
        assert "diffusion_reconstruction_score" in result.model_input
        assert "semantic_consistency_score" in result.model_input


class TestJPEGArtifactAnalysis:
    @staticmethod
    def _jpeg_bytes(image: Image.Image, *, quality: int) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, subsampling=0)
        return buffer.getvalue()

    @staticmethod
    def _textured_image(size: tuple[int, int] = (192, 192)) -> Image.Image:
        width, height = size
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        red = 80 + x_coords * 0.55 + 18 * np.sin(y_coords / 9)
        green = 90 + y_coords * 0.45 + 16 * np.cos(x_coords / 13)
        blue = 120 + (x_coords + y_coords) * 0.25 + 10 * np.sin((x_coords + y_coords) / 11)
        noise = np.random.default_rng(7).normal(0, 4, (height, width))
        pixels = np.stack([red + noise, green + noise, blue + noise], axis=2)
        return Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB")

    def test_scores_localized_recompression_above_clean_baseline(self):
        base_image = self._textured_image()
        clean_bytes = self._jpeg_bytes(base_image, quality=92)

        recompressed_base = Image.open(io.BytesIO(clean_bytes)).convert("RGB")
        patch = recompressed_base.crop((64, 64, 136, 136))
        low_quality_patch = Image.open(io.BytesIO(self._jpeg_bytes(patch, quality=25))).convert("RGB")
        manipulated = recompressed_base.copy()
        manipulated.paste(low_quality_patch, (64, 64))
        manipulated_bytes = self._jpeg_bytes(manipulated, quality=95)

        clean = analyze_jpeg_artifacts(
            image_bytes=clean_bytes,
            mime_type="image/jpeg",
            request_id="clean",
        )
        edited = analyze_jpeg_artifacts(
            image_bytes=manipulated_bytes,
            mime_type="image/jpeg",
            request_id="edited",
        )

        assert edited.score > clean.score + 0.15
        assert edited.metrics["block_inconsistency_score"] == edited.score
        assert edited.verdict == "suspicious"
        assert edited.artifact_map.data_url.startswith("data:image/png;base64,")
        assert edited.regions

    def test_moderate_score_without_grid_mismatch_is_clean(self):
        verdict = _verdict_for_metrics(
            raw_score=0.57,
            source_is_jpeg=True,
            strongest_region_delta=0.18,
            boundary_grid_strength=0.04,
        )

        assert verdict == "clean"

    def test_borderline_score_with_partial_support_is_inconclusive(self):
        verdict = _verdict_for_metrics(
            raw_score=0.65,
            source_is_jpeg=True,
            strongest_region_delta=0.2,
            boundary_grid_strength=0.04,
        )

        assert verdict == "inconclusive"

    def test_localized_grid_mismatch_remains_suspicious(self):
        verdict = _verdict_for_metrics(
            raw_score=0.51,
            source_is_jpeg=True,
            strongest_region_delta=0.31,
            boundary_grid_strength=0.21,
        )

        assert verdict == "suspicious"

    def test_non_jpeg_can_still_report_strong_compression_evidence(self):
        verdict = _verdict_for_metrics(
            raw_score=0.72,
            source_is_jpeg=False,
            strongest_region_delta=0.35,
            boundary_grid_strength=0.18,
        )

        assert verdict == "suspicious"


class TestProvenanceAnalysis:
    @staticmethod
    def _png_bytes_with_metadata(metadata: dict[str, str] | None = None) -> bytes:
        image = Image.new("RGB", (24, 24), color=(130, 140, 150))
        buffer = io.BytesIO()
        if metadata:
            png_info = PngImagePlugin.PngInfo()
            for key, value in metadata.items():
                png_info.add_text(key, value)
            image.save(buffer, format="PNG", pnginfo=png_info)
        else:
            image.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_detects_explicit_ai_provenance_metadata(self):
        image_bytes = self._png_bytes_with_metadata(
            {
                "Software": "OpenAI DALL-E",
                "Generator": "ChatGPT image generation",
            }
        )

        analysis = analyze_provenance(
            image_bytes=image_bytes,
            mime_type="image/png",
            request_id="provenance-ai",
        )
        forensic_test = analysis.to_forensic_test()

        assert analysis.verdict == "suspicious"
        assert analysis.score >= 0.95
        assert analysis.confidence >= 0.9
        assert "OpenAI / DALL-E" in analysis.indicators
        assert forensic_test["test_name"] == "Provenance / Watermark Analysis"
        assert forensic_test["details"]["metrics"]["ai_metadata_present"] is True

    def test_missing_provenance_metadata_stays_clean_without_claiming_real(self):
        analysis = analyze_provenance(
            image_bytes=self._png_bytes_with_metadata(),
            mime_type="image/png",
            request_id="provenance-clean",
        )

        assert analysis.verdict == "clean"
        assert analysis.score == 0.0
        assert analysis.indicators == []
        assert "AI generation is still possible" in analysis.explanation

    def test_generic_generation_fields_are_inconclusive(self):
        analysis = analyze_provenance(
            image_bytes=self._png_bytes_with_metadata({"prompt": "a dramatic mountain at sunset"}),
            mime_type="image/png",
            request_id="provenance-prompt",
        )

        assert analysis.verdict == "inconclusive"
        assert 0.0 < analysis.score < 0.6

    def test_verified_c2pa_ai_action_is_suspicious(self, monkeypatch):
        monkeypatch.setattr(
            "backend.detector.provenance._verify_c2pa_with_tool",
            lambda image_bytes, mime_type: {
                "c2pa_verification_status": "valid",
                "c2pa_signature_valid": True,
                "c2pa_ai_action_present": True,
                "c2pa_camera_capture_claim_present": False,
                "c2pa_claim_generator": "OpenAI",
                "c2pa_signer": "OpenAI",
                "c2pa_tool_used": "c2patool",
            },
        )

        analysis = analyze_provenance(
            image_bytes=self._png_bytes_with_metadata(),
            mime_type="image/png",
            request_id="provenance-c2pa-ai",
        )

        assert analysis.verdict == "suspicious"
        assert analysis.metrics["c2pa_verification_status"] == "valid"
        assert analysis.metrics["c2pa_signature_valid"] is True
        assert analysis.metrics["c2pa_ai_action_present"] is True
        assert "verified C2PA AI action" in analysis.indicators

    def test_invalid_c2pa_ai_claim_reduces_confidence(self, monkeypatch):
        monkeypatch.setattr(
            "backend.detector.provenance._verify_c2pa_with_tool",
            lambda image_bytes, mime_type: {
                "c2pa_verification_status": "invalid",
                "c2pa_signature_valid": False,
                "c2pa_ai_action_present": True,
                "c2pa_camera_capture_claim_present": False,
                "c2pa_claim_generator": "OpenAI",
                "c2pa_signer": "OpenAI",
                "c2pa_tool_used": "c2patool",
            },
        )

        analysis = analyze_provenance(
            image_bytes=self._png_bytes_with_metadata(
                {
                    "Content Credentials": "OpenAI generated image",
                    "prompt": "a dramatic mountain at sunset",
                }
            ),
            mime_type="image/png",
            request_id="provenance-c2pa-invalid",
        )

        assert analysis.verdict == "inconclusive"
        assert analysis.score < 0.7
        assert analysis.confidence < 0.9
        assert "invalid or tampered C2PA manifest" in analysis.indicators
        assert "unverified C2PA AI action" in analysis.indicators
        assert "verified C2PA AI action" not in analysis.indicators


class TestAISpecificEvidenceAnalysis:
    @staticmethod
    def _png_bytes(image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _photo_like_image(size: tuple[int, int] = (160, 160), *, seed: int = 31) -> Image.Image:
        width, height = size
        rng = np.random.default_rng(seed)
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        red = 74 + x_coords * 0.46 + 12 * np.sin(y_coords / 10) + rng.normal(0, 5, (height, width))
        green = 86 + y_coords * 0.4 + 10 * np.cos(x_coords / 13) + rng.normal(0, 5, (height, width))
        blue = 112 + (x_coords + y_coords) * 0.14 + rng.normal(0, 5, (height, width))
        pixels = np.stack([red, green, blue], axis=2)
        return Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB")

    def test_frequency_fingerprint_returns_ui_ready_map(self):
        width, height = 160, 160
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        pattern = ((x_coords % 8 < 4) ^ (y_coords % 8 < 4)).astype(np.float64) * 70
        image = Image.fromarray(np.clip(90 + pattern, 0, 255).astype("uint8"), "L").convert("RGB")

        clean = analyze_frequency_fingerprint(
            image_bytes=self._png_bytes(self._photo_like_image()),
            request_id="freq-clean",
        )
        patterned = analyze_frequency_fingerprint(
            image_bytes=self._png_bytes(image),
            request_id="freq-pattern",
        )

        assert 0.0 <= clean.score <= 1.0
        assert patterned.score >= clean.score
        assert patterned.artifact_map.data_url.startswith("data:image/png;base64,")
        assert patterned.to_forensic_test()["test_name"] == "AI Frequency Fingerprint Analysis"

    def test_diffusion_reconstruction_proxy_discloses_lack_of_true_model(self):
        image = self._photo_like_image()

        analysis = analyze_diffusion_reconstruction(
            image_bytes=self._png_bytes(image),
            request_id="diffusion-proxy",
        )

        assert 0.0 <= analysis.score <= 1.0
        assert 0.0 <= analysis.confidence <= 1.0
        assert analysis.metrics["true_diffusion_model_available"] is False
        assert analysis.artifact_map.data_url.startswith("data:image/png;base64,")
        assert analysis.to_forensic_test()["test_name"] == "Diffusion Reconstruction Analysis"

    def test_semantic_consistency_proxy_discloses_lack_of_vlm(self):
        image = Image.new("RGB", (160, 160), (120, 128, 136))
        draw = ImageDraw.Draw(image)
        for offset in range(8, 150, 16):
            draw.line((8, offset, 150, 160 - offset), fill=(245, 245, 245), width=2)
            draw.rectangle((offset, 12, offset + 8, 32), outline=(20, 20, 20), width=1)

        analysis = analyze_semantic_consistency(
            image_bytes=self._png_bytes(image),
            request_id="semantic-proxy",
        )

        assert 0.0 <= analysis.score <= 1.0
        assert 0.0 <= analysis.confidence <= 1.0
        assert analysis.metrics["vlm_model_available"] is False
        assert analysis.artifact_map.data_url.startswith("data:image/png;base64,")
        assert analysis.to_forensic_test()["test_name"] == "Semantic Consistency Analysis"


class TestElaAnalysis:
    @staticmethod
    def _jpeg_bytes(image: Image.Image, *, quality: int) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, subsampling=0)
        return buffer.getvalue()

    @staticmethod
    def _photo_like_image(size: tuple[int, int] = (256, 256)) -> Image.Image:
        width, height = size
        rng = np.random.default_rng(11)
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        red = 70 + x_coords * 0.42 + rng.normal(0, 5, (height, width))
        green = 84 + y_coords * 0.36 + rng.normal(0, 5, (height, width))
        blue = 112 + (x_coords + y_coords) * 0.16 + rng.normal(0, 5, (height, width))
        pixels = np.stack([red, green, blue], axis=2)
        return Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB").filter(
            ImageFilter.GaussianBlur(0.7)
        )

    def test_pasted_smooth_object_scores_above_clean_baseline(self):
        base_image = self._photo_like_image()
        clean_bytes = self._jpeg_bytes(base_image, quality=85)

        edited = Image.open(io.BytesIO(clean_bytes)).convert("RGB")
        patch = Image.new("RGB", (74, 64), (235, 235, 245))
        draw = ImageDraw.Draw(patch)
        draw.ellipse((8, 8, 66, 56), fill=(30, 120, 230))
        draw.rectangle((28, 18, 48, 48), fill=(250, 60, 60))
        edited.paste(patch, (78, 72))
        edited_bytes = self._jpeg_bytes(edited, quality=85)

        clean = analyze_ela(image_bytes=clean_bytes, request_id="clean")
        pasted = analyze_ela(image_bytes=edited_bytes, request_id="pasted")

        assert pasted.score > clean.score + 25.0
        assert pasted.verdict == "suspicious"
        assert pasted.to_forensic_test()["test_name"] == "Error Level Analysis"
        assert pasted.to_forensic_test()["details"]["artifact_map"]["url"].startswith("data:image/png;base64,")

    def test_moderate_ela_score_without_hotspot_support_stays_clean(self):
        verdict = _ela_verdict_for_metrics(
            score=32.2,
            localized_peak_delta=0.62,
            localized_max_delta=1.1,
            localized_hotspot_ratio=0.0,
            smooth_peak_delta=0.2,
            smooth_max_delta=0.5,
            smooth_localized_hotspot_ratio=0.0,
            hotspot_ratio_pct=0.0,
        )

        assert verdict == "clean"

    def test_moderate_ela_score_with_hotspot_support_is_inconclusive(self):
        verdict = _ela_verdict_for_metrics(
            score=48.0,
            localized_peak_delta=0.95,
            localized_max_delta=1.4,
            localized_hotspot_ratio=0.0,
            smooth_peak_delta=0.98,
            smooth_max_delta=1.4,
            smooth_localized_hotspot_ratio=0.3,
            hotspot_ratio_pct=0.0,
        )

        assert verdict == "inconclusive"

    def test_textured_hotspots_without_smooth_support_stay_clean(self):
        verdict = _ela_verdict_for_metrics(
            score=79.7,
            localized_peak_delta=1.4,
            localized_max_delta=3.2,
            localized_hotspot_ratio=2.5,
            smooth_peak_delta=0.2,
            smooth_max_delta=0.4,
            smooth_localized_hotspot_ratio=0.0,
            hotspot_ratio_pct=0.0,
        )

        assert verdict == "clean"

    def test_high_texture_outdoor_scene_stays_clean(self):
        rng = np.random.default_rng(23)
        width, height = 256, 256
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        base = np.stack(
            [
                80 + x_coords * 0.18 + rng.normal(0, 18, (height, width)),
                95 + y_coords * 0.16 + rng.normal(0, 18, (height, width)),
                110 + (x_coords + y_coords) * 0.08 + rng.normal(0, 18, (height, width)),
            ],
            axis=2,
        )
        image = Image.fromarray(np.clip(base, 0, 255).astype("uint8"), "RGB").filter(
            ImageFilter.GaussianBlur(0.35)
        )
        draw = ImageDraw.Draw(image)
        for _ in range(35):
            draw.line(
                (
                    int(rng.integers(0, width)),
                    int(rng.integers(0, height)),
                    int(rng.integers(0, width)),
                    int(rng.integers(0, height)),
                ),
                fill=(20, 30, 25),
                width=int(rng.integers(1, 3)),
            )
        for _ in range(120):
            draw.point(
                (int(rng.integers(0, width)), int(rng.integers(0, height))),
                fill=(245, 245, 230),
            )

        analysis = analyze_ela(
            image_bytes=self._jpeg_bytes(image, quality=86),
            request_id="natural-texture",
        )

        assert analysis.verdict == "clean"


class TestNoiseTextureAnalysis:
    @staticmethod
    def _png_bytes(image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _photo_like_image(
        size: tuple[int, int] = (192, 192),
        *,
        seed: int = 3,
        noise_sigma: float = 5.0,
    ) -> Image.Image:
        width, height = size
        rng = np.random.default_rng(seed)
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        red = 78 + x_coords * 0.5 + 12 * np.sin(y_coords / 11)
        green = 86 + y_coords * 0.42 + 10 * np.cos(x_coords / 15)
        blue = 112 + (x_coords + y_coords) * 0.18 + 8 * np.sin((x_coords + y_coords) / 13)
        noise = rng.normal(0, noise_sigma, (height, width))
        pixels = np.stack([red + noise, green + noise, blue + noise], axis=2)
        return Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB")

    def test_local_noise_mismatch_scores_above_clean_baseline(self):
        base_image = self._photo_like_image()
        edited_pixels = np.asarray(base_image).astype(np.float64)
        rng = np.random.default_rng(44)
        noisy_patch = rng.normal(0, 28, (72, 72, 1))
        edited_pixels[60:132, 60:132, :] = np.clip(
            edited_pixels[60:132, 60:132, :] + noisy_patch,
            0,
            255,
        )
        edited_image = Image.fromarray(np.clip(edited_pixels, 0, 255).astype("uint8"), "RGB")

        clean = analyze_noise_texture(
            image_bytes=self._png_bytes(base_image),
            request_id="clean-noise",
        )
        edited = analyze_noise_texture(
            image_bytes=self._png_bytes(edited_image),
            request_id="edited-noise",
        )

        assert edited.score > clean.score + 0.25
        assert edited.score >= 0.45
        assert edited.verdict in {"inconclusive", "suspicious"}
        assert edited.metrics["noise_variance_score"] == edited.score
        assert edited.artifact_map.data_url.startswith("data:image/png;base64,")
        assert edited.to_forensic_test()["test_name"] == "Noise Pattern / Texture Consistency Analysis"
        assert edited.to_forensic_test()["details"]["artifact_map"]["url"].startswith("data:image/png;base64,")

    def test_shadow_noise_shift_stays_clean(self):
        base_image = self._photo_like_image()
        pixels = np.asarray(base_image).astype(np.float64)
        rng = np.random.default_rng(51)
        pixels[:, :88, :] = np.clip(
            (pixels[:, :88, :] * 0.62) + rng.normal(0, 3, (192, 88, 1)),
            0,
            255,
        )
        shadow_image = Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB")

        analysis = analyze_noise_texture(
            image_bytes=self._png_bytes(shadow_image),
            request_id="shadow-noise",
        )

        assert analysis.verdict == "clean"
        assert analysis.score < 0.25

    @pytest.mark.parametrize("size", [(12, 12), (640, 96), (900, 500)])
    def test_handles_varied_resolutions(self, size):
        analysis = analyze_noise_texture(
            image_bytes=self._png_bytes(self._photo_like_image(size=size)),
            request_id=f"noise-{size[0]}x{size[1]}",
        )

        assert 0.0 <= analysis.score <= 1.0
        assert 0.0 <= analysis.confidence <= 1.0
        assert analysis.verdict in {"clean", "inconclusive", "suspicious"}
        assert analysis.metrics["analyzed_blocks"] >= 1.0
        assert analysis.artifact_map.data_url.startswith("data:image/png;base64,")

    def test_verdict_requires_local_transition_support(self):
        verdict = _noise_verdict_for_metrics(
            raw_score=0.62,
            strongest_region_delta=0.24,
            transition_strength=0.03,
            suspicious_ratio=0.0,
        )

        assert verdict == "clean"


class TestCopyMoveAnalysis:
    @staticmethod
    def _png_bytes(image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _textured_image(size: tuple[int, int] = (220, 220), *, seed: int = 9) -> Image.Image:
        width, height = size
        rng = np.random.default_rng(seed)
        y_coords, x_coords = np.mgrid[0:height, 0:width]
        red = 70 + x_coords * 0.48 + 18 * np.sin(y_coords / 8) + rng.normal(0, 6, (height, width))
        green = 86 + y_coords * 0.36 + 12 * np.cos(x_coords / 10) + rng.normal(0, 6, (height, width))
        blue = 116 + (x_coords + y_coords) * 0.12 + 9 * np.sin((x_coords - y_coords) / 12)
        blue = blue + rng.normal(0, 6, (height, width))
        pixels = np.stack([red, green, blue], axis=2)
        return Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB")

    def test_detects_known_copy_move_clone_regions(self):
        base_image = self._textured_image()
        cloned = base_image.copy()
        cloned.paste(base_image.crop((42, 50, 102, 110)), (130, 118))

        clean = analyze_copy_move(
            image_bytes=self._png_bytes(base_image),
            request_id="clean-copy-move",
        )
        edited = analyze_copy_move(
            image_bytes=self._png_bytes(cloned),
            request_id="edited-copy-move",
        )

        assert clean.verdict == "clean"
        assert edited.score > clean.score + 0.5
        assert edited.verdict == "suspicious"
        assert edited.metrics["clone_score"] == edited.score
        assert edited.metrics["strongest_cluster_matches"] >= 8.0
        assert edited.metrics["strongest_cluster_rmse"] <= 5.5
        assert edited.artifact_map.data_url.startswith("data:image/png;base64,")
        assert len(edited.regions) >= 2
        assert edited.clone_pairs
        assert edited.to_forensic_test()["test_name"] == "Copy-Move (Clone) Detection"
        assert edited.to_forensic_test()["details"]["artifact_map"]["url"].startswith("data:image/png;base64,")

    def test_handles_small_images_without_clone_regions(self):
        analysis = analyze_copy_move(
            image_bytes=self._png_bytes(self._textured_image(size=(32, 32))),
            request_id="small-copy-move",
        )

        assert 0.0 <= analysis.score <= 1.0
        assert 0.0 <= analysis.confidence <= 1.0
        assert analysis.verdict in {"clean", "inconclusive", "suspicious"}
        assert analysis.artifact_map.data_url.startswith("data:image/png;base64,")

    def test_repeated_real_scene_patterns_stay_clean(self):
        image = Image.new("RGB", (260, 220), (120, 130, 135))
        draw = ImageDraw.Draw(image)
        rng = np.random.default_rng(101)
        for top in range(18, 190, 46):
            for left in range(18, 235, 46):
                shade = int(80 + rng.integers(-8, 9))
                draw.rectangle((left, top, left + 25, top + 25), fill=(shade, shade + 30, shade + 55))
                draw.line((left + 3, top + 20, left + 21, top + 5), fill=(shade + 70, shade + 60, shade + 45), width=2)

        pixels = np.asarray(image).astype(np.float64)
        pixels += rng.normal(0, 5, pixels.shape)
        repeated_scene = Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"), "RGB")

        analysis = analyze_copy_move(
            image_bytes=self._png_bytes(repeated_scene),
            request_id="repeated-real-scene",
        )

        assert analysis.verdict == "clean"
        assert analysis.regions == []
        assert analysis.clone_pairs == []

    def test_verdict_requires_high_similarity_support(self):
        verdict = _copy_move_verdict_for_metrics(
            raw_score=0.74,
            match_count=36,
            coherence=1.0,
            region_area_ratio=0.1,
            mean_similarity=0.937,
            mean_photometric_rmse=4.0,
        )

        assert verdict == "clean"

    def test_verdict_requires_low_photometric_error(self):
        verdict = _copy_move_verdict_for_metrics(
            raw_score=0.74,
            match_count=36,
            coherence=1.0,
            region_area_ratio=0.1,
            mean_similarity=0.99,
            mean_photometric_rmse=9.0,
        )

        assert verdict == "clean"


class TestVlmSemanticAnalysis:
    @staticmethod
    def _png_bytes() -> bytes:
        image = Image.new("RGB", (32, 32), color=(120, 130, 140))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def test_vlm_disabled_without_key_or_flag(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DETECTOR_ENABLE_VLM", raising=False)

        assert should_run_vlm_semantic() is False

    def test_vlm_stays_disabled_with_key_until_flag_is_on(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.delenv("DETECTOR_ENABLE_VLM", raising=False)

        assert should_run_vlm_semantic() is False

    def test_vlm_enabled_with_explicit_flag(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("DETECTOR_ENABLE_VLM", "1")

        assert should_run_vlm_semantic() is True

    def test_openai_vlm_response_maps_to_suspicious(self, monkeypatch):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "output_text": json.dumps(
                        {
                            "ai_likelihood": 82,
                            "confidence": 76,
                            "visible_artifact_count": 3,
                            "text_anomaly_present": True,
                            "anatomy_anomaly_present": False,
                            "reflection_or_shadow_anomaly_present": True,
                            "geometry_or_perspective_anomaly_present": False,
                            "notable_observations": [
                                "Readable text appears malformed.",
                                "Reflections do not match nearby objects.",
                            ],
                            "reasoning_summary": "The image has visible text and reflection anomalies worth reviewing.",
                        }
                    )
                }

        captured: dict[str, object] = {}

        def fake_post(url, *, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["payload"] = json
            captured["headers"] = headers
            captured["timeout"] = timeout
            return Response()

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("OPENAI_VLM_MODEL", "gpt-test-vision")
        monkeypatch.setattr("backend.detector.vlm_semantic.requests.post", fake_post)

        analysis = analyze_vlm_semantic(
            image_bytes=self._png_bytes(),
            mime_type="image/png",
            request_id="vlm-review",
        )

        assert analysis.verdict == "suspicious"
        assert analysis.score == pytest.approx(0.82)
        assert analysis.confidence == pytest.approx(0.76)
        assert analysis.metrics["vlm_model_available"] is True
        assert analysis.metrics["vlm_model"] == "gpt-test-vision"
        assert analysis.metrics["text_anomaly_present"] is True
        assert len(analysis.observations) == 2
        assert captured["url"] == "https://api.openai.com/v1/responses"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        payload = captured["payload"]
        assert payload["text"]["format"]["type"] == "json_schema"
        assert payload["input"][0]["content"][1]["type"] == "input_image"
        assert payload["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")

    def test_low_confidence_without_visual_artifacts_stays_clean(self, monkeypatch):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "output_text": json.dumps(
                        {
                            "ai_likelihood": 10,
                            "confidence": 30,
                            "visible_artifact_count": 0,
                            "text_anomaly_present": False,
                            "anatomy_anomaly_present": False,
                            "reflection_or_shadow_anomaly_present": False,
                            "geometry_or_perspective_anomaly_present": False,
                            "notable_observations": [
                                "No obvious visual artifacts were detected.",
                            ],
                            "reasoning_summary": "No concrete visible artifacts were found.",
                        }
                    )
                }

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setattr("backend.detector.vlm_semantic.requests.post", lambda *args, **kwargs: Response())

        analysis = analyze_vlm_semantic(
            image_bytes=self._png_bytes(),
            mime_type="image/png",
            request_id="vlm-low-confidence-clean",
        )

        assert analysis.verdict == "clean"
        assert analysis.score == pytest.approx(0.1)
        assert analysis.confidence == pytest.approx(0.3)
        assert "weak review signal" in analysis.explanation

    def test_missing_key_returns_unavailable_review(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        analysis = analyze_vlm_semantic(
            image_bytes=self._png_bytes(),
            mime_type="image/png",
            request_id="vlm-missing-key",
        )

        assert analysis.verdict == "inconclusive"
        assert analysis.score == 0.0
        assert analysis.confidence == 0.0
        assert analysis.metrics["vlm_model_available"] is False


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

    def test_provider_real_verdict_with_high_score_becomes_low_ai_probability(self, monkeypatch):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"is_ai": False, "score": 91.9}

        monkeypatch.setenv("BITMIND_API_KEY", "test-key")
        monkeypatch.setattr("backend.detector.predict.requests.post", lambda *args, **kwargs: Response())

        result = predict_scores(
            model_input={"entropy": 1.0},
            metadata={"image_bytes": b"123", "mime_type": "image/png"},
            allow_fallback=False,
        )

        assert result.ai_probability == pytest.approx(8.1)
        assert result.raw_scores["provider_confidence"] == pytest.approx(91.9)
        assert result.raw_scores["provider_is_ai"] is False

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


class TestEvidenceSummary:
    def test_model_evidence_reports_provider_and_signal_strength(self):
        prediction = PredictionOutput(
            ai_probability=8.1,
            raw_scores={
                "ai_probability": 8.1,
                "provider_score": 91.9,
                "provider_confidence": 91.9,
                "provider_is_ai": False,
            },
            model_name="bitmind_api",
            used_fallback=False,
        )

        evidence = build_model_evidence(prediction=prediction, threshold=60.0)

        assert evidence["provider"] == "bitmind_api"
        assert evidence["rawAiProbability"] == pytest.approx(8.1)
        assert evidence["providerVerdict"] == "Low AI Signal"
        assert evidence["signalStrength"] == "strong"

    def test_reliability_drops_for_unstable_robustness(self):
        reliability = assess_result_reliability(
            model_evidence={
                "providerConfidence": 94.0,
                "signalStrength": "strong",
                "usedFallback": False,
            },
            final_is_ai=False,
            response_confidence=94.0,
            forensic_tests=[],
            robustness={"status": "unstable"},
        )

        assert reliability["level"] in {"low", "inconclusive"}
        assert reliability["score"] <= 58.0


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
        assert result.indicators == []
