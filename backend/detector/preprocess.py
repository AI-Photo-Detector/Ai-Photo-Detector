import math
from dataclasses import dataclass
from typing import Any


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


def preprocess_image(*, image_bytes: bytes, mime_type: str, deterministic: bool = False) -> PreprocessOutput:
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

    return PreprocessOutput(model_input=model_input, metadata=metadata)
