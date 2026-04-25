import math
from dataclasses import dataclass
from typing import Any

from backend.detector.exif_metadata import analyze_exif_metadata
from backend.detector.resampling_detection import analyze_resampling_detection
from backend.detector.copy_move import analyze_copy_move
from backend.detector.diffusion_reconstruction import analyze_diffusion_reconstruction
from backend.detector.ela import analyze_ela
from backend.detector.frequency_fingerprint import analyze_frequency_fingerprint
from backend.detector.jpeg_artifacts import analyze_jpeg_artifacts
from backend.detector.noise_texture import analyze_noise_texture
from backend.detector.provenance import analyze_provenance
from backend.detector.semantic_consistency import analyze_semantic_consistency
from backend.detector.edge_boundary import analyze_edge_boundary
from backend.detector.vlm_semantic import analyze_vlm_semantic, should_run_vlm_semantic


# Basic magic-byte checks keep preprocessing dependency-free.
SIGNATURES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}


@dataclass(frozen=True)
class PreprocessOutput:
    model_input: dict[str, float]
    metadata: dict[str, Any]


def _entropy(sample: bytes) -> float:
    if not sample:
        return 0.0

    histogram = [0] * 256
    for b in sample:
        histogram[b] += 1

    sample_size = len(sample)
    entropy = 0.0
    for count in histogram:
        if count:
            p = count / sample_size
            entropy -= p * math.log2(p)
    return entropy


def preprocess_image(
    *,
    image_bytes: bytes,
    mime_type: str,
    request_id: str | None = None,
    deterministic: bool = False,
) -> PreprocessOutput:
    if not image_bytes:
        raise ValueError("Uploaded image is empty.")

    expected_signatures = SIGNATURES.get(mime_type, [])
    if not expected_signatures:
        raise ValueError("Unsupported MIME type for preprocessing.")

    if not any(image_bytes.startswith(sig) for sig in expected_signatures):
        webp_valid = mime_type == "image/webp" and image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP"
        if not webp_valid:
            raise ValueError("File content does not match declared MIME type.")

    byte_length = len(image_bytes)
    zero_ratio = image_bytes.count(0) / byte_length
    sample = image_bytes[: min(4096, byte_length)]
    entropy = _entropy(sample)

    model_input = {
        "entropy": entropy,
        "zero_ratio": zero_ratio,
        "size_log": math.log1p(byte_length),
        "size_norm": min(1.0, byte_length / (10 * 1024 * 1024)),
    }

    metadata = {
        "mime_type": mime_type,
        "byte_length": byte_length,
        "deterministic": deterministic,
    }

    if request_id:
        exif_metadata_analysis = analyze_exif_metadata(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        provenance_analysis = analyze_provenance(
            image_bytes=image_bytes,
            mime_type=mime_type,
            request_id=request_id,
        )
        frequency_fingerprint_analysis = analyze_frequency_fingerprint(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        diffusion_reconstruction_analysis = analyze_diffusion_reconstruction(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        semantic_consistency_analysis = analyze_semantic_consistency(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        vlm_semantic_analysis = (
            analyze_vlm_semantic(
                image_bytes=image_bytes,
                mime_type=mime_type,
                request_id=request_id,
            )
            if should_run_vlm_semantic()
            else None
        )
        ela_analysis = analyze_ela(image_bytes=image_bytes, request_id=request_id)
        jpeg_artifact_analysis = analyze_jpeg_artifacts(
            image_bytes=image_bytes,
            mime_type=mime_type,
            request_id=request_id,
        )
        noise_texture_analysis = analyze_noise_texture(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        resampling_detection_analysis = analyze_resampling_detection(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        edge_boundary_analysis = analyze_edge_boundary(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        copy_move_analysis = analyze_copy_move(
            image_bytes=image_bytes,
            request_id=request_id,
        )
        # We do NOT add EXIF to model_input. EXIF is metadata, it should NOT influence core model scoring
        model_input["ela_anomaly_score"] = ela_analysis.score
        model_input["jpeg_compression_inconsistency_score"] = jpeg_artifact_analysis.score
        model_input["noise_texture_inconsistency_score"] = noise_texture_analysis.score
        model_input["resampling_scaling_score"] = resampling_detection_analysis.score
        model_input["edge_boundary_inconsistency_score"] = edge_boundary_analysis.score
        model_input["copy_move_clone_score"] = copy_move_analysis.score
        model_input["provenance_ai_score"] = provenance_analysis.score
        model_input["frequency_fingerprint_score"] = frequency_fingerprint_analysis.score
        model_input["diffusion_reconstruction_score"] = diffusion_reconstruction_analysis.score
        model_input["semantic_consistency_score"] = semantic_consistency_analysis.score
        if vlm_semantic_analysis is not None:
            model_input["vlm_visual_ai_score"] = vlm_semantic_analysis.score
        metadata["ela"] = {
            "score": ela_analysis.score,
            "explanation": ela_analysis.explanation,
            "metrics": ela_analysis.metrics,
            "heatmap": {
                "url": ela_analysis.heatmap.data_url,
                "mediaType": ela_analysis.heatmap.media_type,
            },
        }
        metadata["forensic_tests"] = [
            provenance_analysis.to_forensic_test(),
            exif_metadata_analysis.to_forensic_test(),
            frequency_fingerprint_analysis.to_forensic_test(),
            diffusion_reconstruction_analysis.to_forensic_test(),
            semantic_consistency_analysis.to_forensic_test(),
            *([vlm_semantic_analysis.to_forensic_test()] if vlm_semantic_analysis is not None else []),
            ela_analysis.to_forensic_test(),
            jpeg_artifact_analysis.to_forensic_test(),
            noise_texture_analysis.to_forensic_test(),
            resampling_detection_analysis.to_forensic_test(),
            edge_boundary_analysis.to_forensic_test(),
            copy_move_analysis.to_forensic_test(),
        ]

    return PreprocessOutput(model_input=model_input, metadata=metadata)
