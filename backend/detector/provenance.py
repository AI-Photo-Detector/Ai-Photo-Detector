import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any

from PIL import Image

try:
    import c2pa
    from c2pa import C2paError
except ImportError:  # pragma: no cover - optional provenance dependency
    c2pa = None
    C2paError = Exception


TEST_NAME = "Provenance / Watermark Analysis"
MAX_METADATA_VALUE_LENGTH = 360
MAX_INDICATORS = 8


AI_PROVENANCE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("OpenAI / DALL-E", ("openai", "dall-e", "dalle", "chatgpt")),
    ("Adobe Firefly", ("firefly", "adobe firefly")),
    ("Google SynthID", ("synthid",)),
    ("Google Imagen", ("google imagen", "imagen 2", "imagen 3", "imagen 4")),
    ("Midjourney", ("midjourney",)),
    ("Stable Diffusion", ("stable diffusion", "sdxl", "automatic1111", "a1111", "invokeai")),
    ("ComfyUI", ("comfyui", "\"workflow\"", "\"prompt\"")),
    ("NovelAI", ("novelai", "nai metadata")),
    ("Runway", ("runwayml", "runway ai")),
    ("Leonardo AI", ("leonardo ai", "leonardo.ai")),
)

C2PA_MARKERS = (
    "c2pa",
    "content credentials",
    "contentcredentials",
    "jumbf",
    "adobe:cai",
    "com.adobe.c2pa",
)

C2PA_AI_ACTION_MARKERS = (
    "trainedalgorithmicmedia",
    "compositewithtrainedalgorithmicmedia",
    "algorithmicmedia",
    "generative ai",
    "ai generated",
    "ai-generated",
    "synthetic",
    "openai",
    "dall-e",
    "dalle",
    "chatgpt",
    "firefly",
    "imagen",
    "midjourney",
    "stable diffusion",
)

C2PA_CAMERA_CAPTURE_MARKERS = (
    "digitalcapture",
    "camera capture",
    "camera-capture",
    "captured",
    "nikon",
    "canon",
    "sony",
    "leica",
    "fujifilm",
)

GENERATOR_METADATA_KEYS = (
    "parameters",
    "prompt",
    "negative_prompt",
    "negative prompt",
    "workflow",
    "software",
    "generator",
    "creator_tool",
    "digital_source_type",
)


@dataclass(frozen=True)
class ProvenanceAnalysis:
    score: float
    confidence: float
    verdict: str
    explanation: str
    metrics: dict[str, float | bool | str]
    indicators: list[str]

    def to_forensic_test(self) -> dict[str, Any]:
        return {
            "test_name": TEST_NAME,
            "score": self.score,
            "confidence": self.confidence,
            "verdict": self.verdict,
            "details": {
                "provenance_score": self.score,
                "explanation": self.explanation,
                "metrics": self.metrics,
                "indicators": self.indicators,
            },
        }


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _decode_bytes_for_scan(image_bytes: bytes) -> str:
    return image_bytes.decode("utf-8", errors="ignore").lower()


def _safe_metadata_value(value: Any) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore")
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_METADATA_VALUE_LENGTH]


def _image_metadata(image_bytes: bytes) -> dict[str, str]:
    metadata: dict[str, str] = {}
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            for key, value in image.info.items():
                if value is None:
                    continue
                metadata[str(key).lower()] = _safe_metadata_value(value)

            exif = image.getexif()
            for key, value in exif.items():
                if value is None:
                    continue
                metadata[f"exif_{key}"] = _safe_metadata_value(value)
    except OSError:
        return metadata
    return metadata


def _find_pattern_sources(search_text: str, metadata: dict[str, str]) -> list[str]:
    matches: list[str] = []
    combined_metadata = " ".join(f"{key}={value}" for key, value in metadata.items()).lower()
    haystack = f"{search_text} {combined_metadata}"

    for source_name, patterns in AI_PROVENANCE_PATTERNS:
        if any(pattern in haystack for pattern in patterns):
            matches.append(source_name)

    return sorted(set(matches))


def _has_c2pa_marker(search_text: str, metadata: dict[str, str]) -> bool:
    combined_metadata = " ".join(f"{key}={value}" for key, value in metadata.items()).lower()
    haystack = f"{search_text} {combined_metadata}"
    return any(marker in haystack for marker in C2PA_MARKERS)


def _has_generator_metadata(metadata: dict[str, str]) -> bool:
    keys = set(metadata)
    if any(any(marker in key for marker in GENERATOR_METADATA_KEYS) for key in keys):
        return True

    joined = " ".join(metadata.values()).lower()
    stable_diffusion_parameter_markers = ("steps:", "sampler:", "cfg scale", "seed:", "model hash")
    return sum(1 for marker in stable_diffusion_parameter_markers if marker in joined) >= 2


def _json_from_text(text: str) -> Any | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _first_matching_json_value(payload: Any, key_markers: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_l = str(key).lower()
            if any(marker in key_l for marker in key_markers):
                if isinstance(value, (str, int, float, bool)):
                    return _safe_metadata_value(value)
                if isinstance(value, dict):
                    nested = _first_matching_json_value(value, key_markers)
                    if nested != "none":
                        return nested
            nested = _first_matching_json_value(value, key_markers)
            if nested != "none":
                return nested
    elif isinstance(payload, list):
        for item in payload:
            nested = _first_matching_json_value(item, key_markers)
            if nested != "none":
                return nested
    return "none"


def _suffix_for_mime_type(mime_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime_type, ".img")


def _c2pa_tool_path() -> str | None:
    configured = os.getenv("C2PA_TOOL_PATH", "").strip()
    if configured:
        return configured
    return shutil.which("c2patool") or shutil.which("c2pa")


def _empty_c2pa_result(
    *,
    status: str,
    tool_used: str,
    signature_valid: bool = False,
    ai_action_present: bool = False,
    camera_capture_claim_present: bool = False,
    claim_generator: str = "none",
    signer: str = "none",
) -> dict[str, str | bool]:
    return {
        "c2pa_verification_status": status,
        "c2pa_signature_valid": signature_valid,
        "c2pa_ai_action_present": ai_action_present,
        "c2pa_camera_capture_claim_present": camera_capture_claim_present,
        "c2pa_claim_generator": claim_generator,
        "c2pa_signer": signer,
        "c2pa_tool_used": tool_used,
    }


def _c2pa_status_from_json(payload: Any) -> str:
    payload_l = json.dumps(payload, sort_keys=True).lower()
    invalid_markers = ("invalid", "tamper", "claim.missing", "assertion.missing", "signature.mismatch")
    valid_markers = ("validation_state", "valid", "trusted", "signingcredential.trusted")

    if any(marker in payload_l for marker in invalid_markers):
        return "invalid"
    if any(marker in payload_l for marker in valid_markers):
        return "valid"
    return "present"


def _verify_c2pa_with_python(image_bytes: bytes, mime_type: str) -> dict[str, str | bool] | None:
    if c2pa is None:
        return None

    tool_used = f"c2pa-python {getattr(c2pa, '__version__', 'unknown')}"
    try:
        reader = c2pa.Reader.try_create(mime_type, io.BytesIO(image_bytes))
        if reader is None:
            return _empty_c2pa_result(status="no_manifest", tool_used=tool_used)

        with reader:
            payload = json.loads(reader.json())
            verification_status = _c2pa_status_from_json(payload)
            json_l = json.dumps(payload, sort_keys=True).lower()
            ai_action_present = any(marker in json_l for marker in C2PA_AI_ACTION_MARKERS)
            camera_capture_claim_present = any(marker in json_l for marker in C2PA_CAMERA_CAPTURE_MARKERS)
            claim_generator = _first_matching_json_value(
                payload,
                ("claim_generator", "claimgenerator", "generator", "softwareagent", "software_agent"),
            )
            signer = _first_matching_json_value(
                payload,
                ("issuer", "signer", "common_name", "commonname", "cert_serial_number"),
            )

            return _empty_c2pa_result(
                status=verification_status,
                tool_used=tool_used,
                signature_valid=verification_status in {"valid", "present"},
                ai_action_present=ai_action_present,
                camera_capture_claim_present=camera_capture_claim_present,
                claim_generator=claim_generator,
                signer=signer,
            )
    except (C2paError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _verify_c2pa_with_cli(image_bytes: bytes, mime_type: str) -> dict[str, str | bool]:
    tool_path = _c2pa_tool_path()
    if not tool_path:
        return _empty_c2pa_result(status="unavailable", tool_used="none")

    try:
        timeout_seconds = float(os.getenv("C2PA_TIMEOUT_SECONDS", "10"))
    except ValueError:
        timeout_seconds = 10.0
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=_suffix_for_mime_type(mime_type)) as temp_file:
            temp_file.write(image_bytes)
            temp_path = temp_file.name

        completed = subprocess.run(
            [tool_path, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return _empty_c2pa_result(status="error", tool_used=tool_path)
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    output = f"{completed.stdout}\n{completed.stderr}"
    output_l = output.lower()
    payload = _json_from_text(output)
    json_l = json.dumps(payload, sort_keys=True).lower() if payload is not None else output_l

    no_manifest_markers = ("no c2pa", "no manifest", "manifest not found", "could not find a manifest")
    if any(marker in output_l for marker in no_manifest_markers):
        verification_status = "no_manifest"
    elif completed.returncode != 0 and any(marker in output_l for marker in ("invalid", "tamper", "validation")):
        verification_status = "invalid"
    elif any(marker in output_l for marker in ("validation_status", "valid", "trusted")):
        verification_status = "valid"
    elif completed.returncode == 0:
        verification_status = "present"
    else:
        verification_status = "unknown"

    signature_valid = verification_status in {"valid", "present"} and "invalid" not in output_l
    ai_action_present = any(marker in json_l for marker in C2PA_AI_ACTION_MARKERS)
    camera_capture_claim_present = any(marker in json_l for marker in C2PA_CAMERA_CAPTURE_MARKERS)

    claim_generator = _first_matching_json_value(payload, ("claim_generator", "claimgenerator", "generator")) if payload else "none"
    signer = _first_matching_json_value(payload, ("issuer", "signer", "common_name", "commonname")) if payload else "none"

    return {
        "c2pa_verification_status": verification_status,
        "c2pa_signature_valid": signature_valid,
        "c2pa_ai_action_present": ai_action_present,
        "c2pa_camera_capture_claim_present": camera_capture_claim_present,
        "c2pa_claim_generator": claim_generator,
        "c2pa_signer": signer,
        "c2pa_tool_used": tool_path,
    }


def _verify_c2pa_with_tool(image_bytes: bytes, mime_type: str) -> dict[str, str | bool]:
    python_result = _verify_c2pa_with_python(image_bytes, mime_type)
    if python_result is not None:
        return python_result
    return _verify_c2pa_with_cli(image_bytes, mime_type)


def _metadata_summary(metadata: dict[str, str]) -> str:
    if not metadata:
        return "none"

    prioritized = [
        key
        for key in metadata
        if any(marker in key for marker in ("software", "generator", "prompt", "parameters", "workflow", "creator"))
    ]
    if prioritized:
        return ", ".join(prioritized[:4])
    return ", ".join(list(metadata.keys())[:4])


def _explanation(verdict: str, indicators: list[str], metadata_field_count: int) -> str:
    if "invalid or tampered C2PA manifest" in indicators:
        return (
            "A C2PA or Content Credentials marker was found, but verification failed. "
            "The provenance claim is not trusted, so treat this as a review signal rather than proof of AI generation."
        )
    if verdict == "suspicious":
        return (
            "AI provenance, watermark metadata, or a verified AI-generation claim was found. This is high-confidence evidence when intact."
        )
    if verdict == "inconclusive":
        return (
            "Generation-related metadata was found, but it was not specific enough to prove AI origin on its own."
        )
    if metadata_field_count == 0:
        return (
            "No provenance or watermark metadata was found. Metadata can be stripped, so AI generation is still possible."
        )
    return (
        "Metadata was present, but no AI provenance or watermark markers were found. AI generation is still possible."
    )


def analyze_provenance(*, image_bytes: bytes, mime_type: str, request_id: str) -> ProvenanceAnalysis:
    metadata = _image_metadata(image_bytes)
    search_text = _decode_bytes_for_scan(image_bytes)
    ai_sources = _find_pattern_sources(search_text, metadata)
    c2pa_present = _has_c2pa_marker(search_text, metadata)
    c2pa_verification = _verify_c2pa_with_tool(image_bytes, mime_type)
    c2pa_ai_action_present = c2pa_verification["c2pa_ai_action_present"] is True
    c2pa_camera_capture_claim_present = c2pa_verification["c2pa_camera_capture_claim_present"] is True
    c2pa_signature_valid = c2pa_verification["c2pa_signature_valid"] is True
    c2pa_invalid = c2pa_verification["c2pa_verification_status"] == "invalid"
    generator_metadata_present = _has_generator_metadata(metadata)

    indicators: list[str] = []
    if c2pa_present:
        indicators.append("C2PA or Content Credentials marker")
    if c2pa_ai_action_present and c2pa_signature_valid and not c2pa_invalid:
        indicators.append("verified C2PA AI action")
    elif c2pa_ai_action_present:
        indicators.append("unverified C2PA AI action")
    if c2pa_camera_capture_claim_present and c2pa_signature_valid:
        indicators.append("valid camera-capture provenance")
    if c2pa_invalid:
        indicators.append("invalid or tampered C2PA manifest")
    indicators.extend(ai_sources)
    if generator_metadata_present and not ai_sources:
        indicators.append("generation metadata fields")

    indicators = sorted(set(indicators))[:MAX_INDICATORS]

    trusted_c2pa_ai_action = c2pa_ai_action_present and c2pa_signature_valid and not c2pa_invalid
    has_untrusted_ai_claim = bool(ai_sources) or c2pa_ai_action_present or (c2pa_present and generator_metadata_present)

    if c2pa_invalid:
        verdict = "inconclusive"
        score = 0.64 if has_untrusted_ai_claim else 0.56
        confidence = 0.66 if has_untrusted_ai_claim else 0.7
    elif ai_sources or trusted_c2pa_ai_action or (c2pa_present and generator_metadata_present):
        verdict = "suspicious"
        score = 0.98
        confidence = 0.96
    elif c2pa_present or generator_metadata_present:
        verdict = "inconclusive"
        score = 0.42
        confidence = 0.74
    elif c2pa_signature_valid and c2pa_camera_capture_claim_present:
        verdict = "clean"
        score = 0.0
        confidence = 0.82
    else:
        verdict = "clean"
        score = 0.0
        confidence = 0.64 if metadata else 0.52

    metadata_field_count = len(metadata)
    metrics: dict[str, float | bool | str] = {
        "c2pa_marker_present": c2pa_present,
        "c2pa_verification_status": c2pa_verification["c2pa_verification_status"],
        "c2pa_signature_valid": c2pa_verification["c2pa_signature_valid"],
        "c2pa_ai_action_present": c2pa_verification["c2pa_ai_action_present"],
        "c2pa_camera_capture_claim_present": c2pa_verification["c2pa_camera_capture_claim_present"],
        "ai_metadata_present": bool(ai_sources),
        "generator_metadata_present": generator_metadata_present,
        "matched_source_count": float(len(ai_sources)),
        "metadata_field_count": float(metadata_field_count),
        "metadata_fields": _metadata_summary(metadata),
        "c2pa_claim_generator": c2pa_verification["c2pa_claim_generator"],
        "c2pa_signer": c2pa_verification["c2pa_signer"],
        "c2pa_tool_used": c2pa_verification["c2pa_tool_used"],
        "source_format": mime_type.replace("image/", "").upper(),
        "request_id": request_id,
    }

    return ProvenanceAnalysis(
        score=round(_clamp(score, 0.0, 1.0), 4),
        confidence=round(_clamp(confidence, 0.0, 1.0), 4),
        verdict=verdict,
        explanation=_explanation(verdict, indicators, metadata_field_count),
        metrics=metrics,
        indicators=indicators,
    )
